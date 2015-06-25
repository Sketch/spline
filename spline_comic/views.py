from collections import defaultdict
from datetime import datetime
from datetime import time
from datetime import timedelta
import os
import os.path

from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlalchemy.orm import joinedload
from pyramid.httpexceptions import HTTPNotFound
from pyramid.httpexceptions import HTTPSeeOther
from pyramid.renderers import render_to_response
from pyramid.view import view_config
import pytz

from spline.models import session
from spline_comic.logic import get_adjacent_pages
from spline_comic.models import Comic
from spline_comic.models import ComicChapter
from spline_comic.models import ComicPage
from spline_comic.models import GalleryFolder
from spline_comic.models import GalleryItem
from spline_comic.models import END_OF_TIME
from spline_comic.models import XXX_HARDCODED_QUEUE
from spline_comic.models import XXX_HARDCODED_TIMEZONE
from spline_comic.models import get_current_publication_date


@view_config(
    route_name='comic.most-recent',
    request_method='GET')
def comic_most_recent(request):
    page = (
        session.query(ComicPage)
        .join(ComicPage.chapter)
        # "Most recent" never includes the queue
        .filter(~ ComicPage.is_queued)
        .order_by(ComicPage.order.desc())
        .first()
    )

    comic = page.chapter.comic
    include_queued = request.has_permission('queue', comic)
    adjacent_pages = get_adjacent_pages(page, include_queued)

    # TODO this is duplicated below lol
    from spline_wiki.models import Wiki
    wiki = Wiki(request.registry.settings['spline.wiki.root'])
    transcript = wiki['!comic-pages'][str(page.id)]['en']

    ns = dict(
        comic=comic,
        page=page,
        transcript=transcript,
        adjacent_pages=adjacent_pages,
    )

    # TODO sometime maybe the landing page will be a little more interesting
    # and this can go away
    if page:
        renderer = 'spline_comic:templates/page.mako'
    else:
        renderer = 'spline_comic:templates/comic-landing.mako'

    return render_to_response(renderer, ns, request=request)


@view_config(
    route_name='comic.page',
    request_method='GET',
    renderer='spline_comic:templates/page.mako')
def comic_page(page, request):
    include_queued = request.has_permission('queue', page.comic)
    if page.is_queued and not include_queued:
        # 404 instead of 403 to prevent snooping
        return HTTPNotFound()

    adjacent_pages = get_adjacent_pages(page, include_queued)

    from spline_wiki.models import Wiki
    wiki = Wiki(request.registry.settings['spline.wiki.root'])
    transcript = wiki['!comic-pages'][str(page.id)]['en']

    return dict(
        comic=page.comic,
        page=page,
        transcript=transcript,
        adjacent_pages=adjacent_pages,
    )


@view_config(
    route_name='comic.archive',
    request_method='GET',
    renderer='spline_comic:templates/archive.mako')
def comic_archive(request):
    return _comic_archive_shared(None, request)


@view_config(
    context=GalleryFolder,
    request_method='GET',
    renderer='spline_comic:templates/archive.mako')
def comic_browse(context, request):
    return _comic_archive_shared(context, request)


def _comic_archive_shared(context, request):
    folders = (
        session.query(GalleryFolder)
        .filter(GalleryFolder.parent == context)
        .options(
            joinedload(GalleryFolder.children)
        )
        .order_by(GalleryFolder.order)
        .all()
    )
    print(folders)
    folder_ids = [folder.id for folder in folders]
    child_folder_ids = [child.id for folder in folders for child in folder.children]
    visible_folder_ids = folder_ids + child_folder_ids

    # TODO hmmm really need to fetch the first page of each chapter, soooomehow
    # TODO also: need to figure out how the title of a chapter works, since for
    # (most...) single-page faux chapters it'll be ignored, right?
    # TODO empty chapters won't appear at all

    # XXX
    comic = session.query(Comic).order_by(Comic.id.asc()).first()

    # TODO this (and maybe other places) don't check for queued
    recent_pages_by_folder = defaultdict(list)
    if folder_ids:
        recent_page_subq = (
            session.query(
                GalleryItem,
                func.rank().over(partition_by=GalleryItem.folder_id, order_by=GalleryItem.order.desc()).label('rank'),
            )
            .filter(GalleryItem.folder_id.in_(folder_ids))
            .subquery()
        )
        GalleryItem_alias = aliased(GalleryItem, recent_page_subq)
        recent_page_q = (
            session.query(GalleryItem_alias)
            .filter(recent_page_subq.c.rank <= 5)
        )
        for item in recent_page_q:
            recent_pages_by_folder[item.folder].append(item)

    first_page_by_folder = {}
    if child_folder_ids:
        recent_page_q = (
            session.query(GalleryItem)
            .filter(GalleryItem.folder_id.in_(child_folder_ids))
            .order_by(GalleryItem.folder_id, GalleryItem.order.asc())
            .distinct(GalleryItem.folder_id)
        )
        first_page_by_folder = {
            page.folder: page
            for page in recent_page_q
        }

    min_max_q = (
        session.query(
            GalleryFolder,
            func.min(GalleryItem.date_published),
            func.max(GalleryItem.date_published),
        )
        .join(GalleryFolder.pages)
        .filter(GalleryItem.folder_id.in_(visible_folder_ids))
        .group_by(GalleryFolder.id)
    )
    tz = XXX_HARDCODED_TIMEZONE
    date_range_by_folder = {
        folder: (
            tz.normalize(mindate.astimezone(tz)),
            tz.normalize(maxdate.astimezone(tz)),
        )
        for (folder, mindate, maxdate) in min_max_q
    }

    return dict(
        comic=comic,
        folders=folders,
        recent_pages_by_folder=recent_pages_by_folder,
        first_page_by_folder=first_page_by_folder,
        date_range_by_folder=date_range_by_folder,
    )


@view_config(
    route_name='comic.admin',
    permission='admin',
    request_method='GET',
    renderer='spline_comic:templates/admin.mako')
def comic_admin(request):
    # Figure out the starting date for the calendar.  We want to show the
    # previous four weeks, and start at the beginning of the week.
    today = get_current_publication_date(XXX_HARDCODED_TIMEZONE)
    weekday_offset = (today.weekday() - 6) % -7
    start = today + timedelta(days=weekday_offset - 7 * 4)

    # Grab "recent" pages -- any posted in the past two weeks OR in the future.
    recent_pages = (
        session.query(ComicPage)
        .join(ComicPage.chapter)
        .filter(ComicPage.date_published >= start.astimezone(pytz.utc))
        .order_by(ComicPage.date_published.desc())
        .all()
    )

    last_queued, queue_next_date = _get_last_queued_date()
    num_queued = sum(1 for page in recent_pages if page.is_queued)

    day_to_page = {page.date_published.date(): page for page in recent_pages}

    chapters = (
        session.query(ComicChapter)
        .order_by(ComicChapter.order.asc())
        .options(
            joinedload('children')
        )
        .all()
    )

    # Express calendar in dates.  Go at least four weeks into the future, OR
    # one week beyond the last queued comic (for some padding).
    calendar_start = start.date()
    calendar_start -= timedelta(days=calendar_start.isoweekday() % 7)
    calendar_end = today.date() + timedelta(days=7 * 4)
    if day_to_page:
        calendar_end = max(calendar_end, max(day_to_page) + timedelta(days=7))

    # TODO really really really need to move configuration out of comics.  this
    # was clever but not clever enough.
    comic = session.query(Comic).order_by(Comic.id.asc()).first()

    return dict(
        comic=comic,
        chapters=chapters,
        num_queued=num_queued,
        last_queued=last_queued,
        queue_next_date=queue_next_date,

        day_to_page=day_to_page,
        calendar_start=calendar_start,
        calendar_end=calendar_end,
    )


# TODO this is crap
def _get_last_queued_date():
    queued_q = (
        session.query(ComicPage)
        .join(ComicPage.chapter)
        .filter(ComicPage.is_queued)
    )

    last_queued = queued_q.order_by(ComicPage.date_published.desc()).first()

    if last_queued:
        queue_end_date = last_queued.date_published
    else:
        queue_end_date = datetime.combine(
            get_current_publication_date(XXX_HARDCODED_TIMEZONE).astimezone(pytz.utc),
            time(),
        )
    if queue_end_date == END_OF_TIME:
        queue_next_date = None
    else:
        weekdays = [int(wd) for wd in XXX_HARDCODED_QUEUE]
        queue_next_date = next(_generate_queue_dates(weekdays, start=queue_end_date))

    return last_queued, queue_next_date


def _generate_queue_dates(days_of_week, start):
    if not days_of_week:
        # Special case: an empty queue means to freeze the queue, which is
        # easily done in practice by dating everything into the far future
        while True:
            yield END_OF_TIME

    days_of_week = set(days_of_week)
    delta = timedelta(days=1)

    d = start
    dow = d.weekday()

    # NB: Never consider today as part of the queue
    while True:
        d += delta
        dow = (dow + 1) % 7

        if dow in days_of_week:
            yield d


@view_config(
    route_name='comic.save-queue',
    permission='admin',
    request_method='POST')
def comic_queue_do(request):
    # TODO this would be easier with a real validator.
    weekdays = []
    for wd in request.POST.getall('weekday'):
        if wd in '0123456':
            weekdays.append(int(wd))

    queued = (
        session.query(ComicPage)
        .join(ComicPage.chapter)
        .filter(ComicPage.is_queued)
        .order_by(ComicPage.order.asc())
        .all()
    )

    new_dates = _generate_queue_dates(weekdays, start=get_current_publication_date(XXX_HARDCODED_TIMEZONE))
    for page, new_date in zip(queued, new_dates):
        page.date_published = datetime.combine(
            new_date, time()).replace(tzinfo=pytz.utc)
        page.timezone = XXX_HARDCODED_TIMEZONE.zone

    comic.config_queue = ''.join(str(wd) for wd in sorted(weekdays))

    # TODO flash message?
    return HTTPSeeOther(location=request.route_url('comic.admin', comic))


@view_config(
    route_name='comic.upload',
    permission='admin',
    request_method='POST')
def comic_upload_do(request):
    # TODO validation and all that boring stuff
    file_upload = request.POST['file']
    fh = file_upload.file

    from spline.feature.filestore import IStorage
    storage = request.registry.queryUtility(IStorage)

    _, ext = os.path.splitext(file_upload.filename)
    filename = storage.store(fh, ext)

    # TODO wire into transaction so the file gets deleted on rollback

    last_chapter = (
        session.query(ComicChapter)
        .filter(ComicChapter.id == int(request.POST['chapter']))
        .one()
    )

    when = request.POST['when']
    if when == 'now':
        date_published = datetime.now(pytz.utc)
    elif when == 'queue':
        last_queued, queue_next_date = _get_last_queued_date()
        date_published = datetime.combine(
            queue_next_date,
            time(tzinfo=XXX_HARDCODED_TIMEZONE),
        )
        date_published = date_published.astimezone(pytz.utc)

    # Fetch next page number and ordering.  Also need to shift everyone else
    # forwards by one if this is bumping the queue.  Blurgh.
    max_order, = (
        session.query(func.max(ComicPage.order))
        .filter(ComicPage.date_published <= date_published)
        .first()
    )
    if max_order is None:
        max_order = 0
    next_order = max_order + 1

    (
        session.query(ComicPage)
        .filter(ComicPage.order >= next_order)
        .update({ComicPage.order: ComicPage.order + 1})
    )

    max_page_number, = (
        session.query(func.max(ComicPage.page_number))
        .with_parent(last_chapter)
        .filter(ComicPage.date_published <= date_published)
        .first()
    )
    if max_page_number is None:
        max_page_number = 0
    next_page_number = max_page_number + 1

    (
        session.query(ComicPage)
        .with_parent(last_chapter)
        .filter(ComicPage.page_number >= next_page_number)
        .update({ComicPage.page_number: ComicPage.page_number + 1})
    )

    page = ComicPage(
        file=os.path.basename(filename),
        chapter=last_chapter,
        author=request.user,
        date_published=date_published,
        timezone=XXX_HARDCODED_TIMEZONE.zone,

        order=next_order,
        page_number=next_page_number,

        # TODO more validation here too
        title=request.POST['title'],
        comment=request.POST['comment'],
    )
    session.add(page)
    session.flush()

    return HTTPSeeOther(location=request.route_url('comic.page', page))


@view_config(
    route_name='comic.admin.folders',
    permission='admin',
    request_method='POST')
def comic_admin_folders_do(request):
    for folder_id, direction in request.POST.items():
        folder = session.query(ComicChapter).get(folder_id)

        # TODO this should verify, somehow, that there's actually something to the left or right to move to
        if direction == "left":
            # Move the folder leftwards, so that its new "right" is one less than its current "left"
            diff = (folder.left - 1) - folder.right
        elif direction == "right":
            # Move the folder rightwards, so that its new "left" is one more than its current "right"
            diff = (folder.right + 1) - folder.left
        else:
            continue

        # TODO this assumes one direction only...  or does it?
        (
            session.query(ComicChapter)
            .filter(ComicChapter.left.between(
                *sorted((folder.left, folder.left + diff))))
            .update({
                ComicChapter.left: ComicChapter.left - diff,
                ComicChapter.right: ComicChapter.right - diff,
            }, synchronize_session=False)
        )

        folder.left += diff
        folder.right += diff
        session.flush()

    return HTTPSeeOther(
        location=request.route_url('comic.admin') + '#manage-folders')
