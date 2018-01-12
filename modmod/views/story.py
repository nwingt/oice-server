import json
import datetime
import os.path
import uuid
import pyramid_safile
import logging
from pyramid.httpexceptions import HTTPForbidden
from cornice import Service
from modmod.exc import ValidationError
from sqlalchemy import func, and_, or_
from sqlalchemy.orm.exc import NoResultFound

from ..models import (
    DBSession,
    FeaturedStory,
    FeaturedStoryQuery,
    Oice,
    Story,
    StoryLocalization,
    StoryQuery,
    StoryFactory,
    StoryTag,
    StoryTagQuery,
    UserQuery,
    UserReadOiceProgress,
    UserReadOiceProgressQuery,
)

from . import (
    check_is_language_valid,
    get_request_user,
)
from .util import (
    normalize_language,
    normalize_story_language,
)

from ..config import (
    get_oice_view_url,
    get_oice_communication_url,
    get_default_lang,
)
from ..operations.script_validator import ScriptValidator
from ..operations.credit import get_story_credit
from ..operations.image_handler import ComposeOgImage
from ..operations.worker import KSBuildWorker
from ..operations.block import count_words_of_block
from ..operations.story import (
    remove_story_localization,
    translate_story,
    translate_story_preview,
)


log = logging.getLogger(__name__)

story_language = Service(name='story_language',
                         path='story/{story_id}/language/{language}',
                         renderer='json',
                         factory=StoryFactory,
                         traverse='/{story_id}')
story_translate = Service(name='story_translate',
                          path='story/{story_id}/translate',
                          renderer='json',
                          factory=StoryFactory,
                          traverse='/{story_id}')
story_list = Service(name='story_list',
                     path='story',
                     renderer='json')
tag_story = Service(name='tag_story',
                    path='tag/story',
                    renderer='json')
story_id = Service(name='story_id',
                   path='story/{story_id}',
                   renderer='json',
                   factory=StoryFactory,
                   traverse='/{story_id}')
story_validate = Service(name='story_validate',
                         path='story/{story_id}/validate',
                         renderer='json',
                         factory=StoryFactory,
                         traverse='/{story_id}')
story_credits = Service(name='story_credits',
                        path='credits/story/{story_id}',
                        renderer='json',
                        factory=StoryFactory,
                        traverse='/{story_id}')
story_id_wordcount = Service(name='story_id_wordcount',
                             path='story/{story_id}/wordcount',
                             renderer='json',
                             factory=StoryFactory,
                             traverse='/{story_id}')
story_build = Service(name='story_build',
                      path='story/{story_id}/build',
                      renderer='json',
                      factory=StoryFactory,
                      traverse='/{story_id}')
story_like = Service(name='story_like',
                     path='story/{story_id}/like',
                     renderer='json',
                     factory=StoryFactory,
                     traverse='/{story_id}')
story_featured = Service(name='story_featured',
                         path='story/featured',
                         renderer='json')
app_story = Service(name='app_story',
                    path='app/story',
                    renderer='json')
app_story_featured = Service(name='app_story_featured',
                             path='app/story/featured',
                             renderer='json')
app_story_v2 = Service(name='app_story_v2',
                       path='v2/app/story',
                       renderer='json')
app_story_progress = Service(name='app_story_id_progress',
                             path='app/story/{story_id}/progress',
                             renderer='json',
                             factory=StoryFactory,
                             traverse='/{story_id}')
app_story_id_episodes = Service(name='app_story_id_episodes',
                                path='app/story/{story_id}/episodes',
                                renderer='json',
                                factory=StoryFactory,
                                traverse='/{story_id}')


def get_request_language(request, user=None):
    if not user:
        user = get_request_user(request)
    return normalize_story_language(request.GET.get('language', user.ui_language if user else get_default_lang()))


def fetch_story_query_language(request, story):
    query_language = request.params.get('language')
    return check_is_language_valid(query_language) if query_language else story.language


@story_id.get(permission='get')
def show_story(request):
    story = request.context
    return {
        "story": story.serialize(fetch_story_query_language(request, story)),
        "message": "ok",
        "code": 200
    }


@story_list.get(permission='get')
def list_story(request):
    user = UserQuery(DBSession).fetch_user_by_email(email=request.authenticated_userid).one()

    return {
        "stories": [p.serialize(fetch_story_query_language(request, p)) for p in user.stories],
        "message": "ok",
        "code": 200
    }


@story_list.post(permission='get')
def add_story(request):
    try:
        user = UserQuery(DBSession).fetch_user_by_email(email=request.authenticated_userid).one()

        story_name = 'My Story'
        if user.language[:2] == 'zh':
            story_name = '我的故事'
        elif user.language[:2] == 'ja':
            story_name = 'マイストーリー'

        story_name = '{} {}'.format(story_name, len(user.stories) + 1)

        story = Story(name=story_name, language=user.language)

        user.stories.append(story)

        DBSession.add(story)

        # flush because we need an ID
        DBSession.flush()

        return {
            "story": story.serialize(),
            "message": "ok",
            "code": 200
        }
    except ValueError as e:
        raise ValidationError(str(e))


@story_id.post(permission='get')
def update_story(request):
    story_id = request.matchdict['story_id']

    try:
        story = StoryQuery(DBSession)\
            .get_story_by_id(story_id)
        query_language = fetch_story_query_language(request, story)

        # Hardcode config for now, does not work
        # if 'config' in request.json_body:
        #     story.config_obj = request.json_body['config']

        if 'meta' in request.POST:
            meta = json.loads(request.POST['meta'])

            if 'name' in meta:
                story.set_name(meta['name'], query_language)
            if 'description' in meta:
                story.set_description(meta['description'], query_language)
            # /* Do not allow change of primary language */
            # if 'language' in meta:
            #     story.language = meta['language']

        if 'coverStorage' in request.POST:
            cover_storage = request.POST['coverStorage']
            factory = pyramid_safile.get_factory()
            extension = os.path.splitext(cover_storage.filename)[1]
            filename = 'cover_storage' + extension
            handle = factory.create_handle(filename, cover_storage.file)
            story.import_handle(handle, query_language)

        if 'titleLogo' in request.POST:
            title_logo = request.POST['titleLogo']
            factory = pyramid_safile.get_factory()
            extension = os.path.splitext(title_logo.filename)[1]
            filename = 'title_logo' + extension
            handle = factory.create_handle(filename, title_logo.file)
            story.import_title_logo_handle(handle)

        if 'heroImage' in request.POST:
            hero_image = request.POST['heroImage']
            factory = pyramid_safile.get_factory()
            extension = os.path.splitext(hero_image.filename)[1]
            filename = 'hero_image' + extension
            handle = factory.create_handle(filename, hero_image.file)
            story.import_hero_image_handle(handle)
        if 'ogImage' in request.POST:
            og_image = request.POST['ogImage']
            factory = pyramid_safile.get_factory()
            extension = os.path.splitext(og_image.filename)[1]
            filename = 'og_image.jpg'
            handle = factory.create_handle(filename, og_image.file)
            ogImageHandler = ComposeOgImage(handle.dst)
            ogImageHandler.run()
            story.import_og_image_handle(handle, query_language)

        DBSession.add(story)
        return {
            'code': 200,
            'story': story.serialize(query_language)
        }

    except ValueError as e:
        raise ValidationError(str(e))


@story_id.delete(permission='set')
def delete_story(request):

    story = request.context

    story.is_deleted = True

    return {
        'code': 200,
        'message': 'ok'
    }


@story_language.get(permission='get')
def get_supported_language(request):
    story = request.context
    return {
        'code': 200,
        'message': 'ok',
        'languages': story.supported_languages,
    }


@story_language.post(permission='get')
def add_new_language(request):
    story = request.context
    language = check_is_language_valid(request.matchdict['language'])
    localization = StoryLocalization(story=story, language=language, name=story.name, description=story.description)
    DBSession.add(localization)
    story.localizations[language] = localization
    return {
        'code': 200,
        'message': 'ok',
        'languages': story.supported_languages,
    }


@story_language.delete(permission='get')
def remove_locale(request):
    story = request.context
    language = check_is_language_valid(request.matchdict['language'])
    remove_story_localization(DBSession, story, language)
    return {
        'code': 200,
        'message': 'ok',
        'languages': story.supported_languages,
    }


@story_translate.post(permission='get')
def post_translate(request):
    story = request.context

    source_language = check_is_language_valid(request.json_body.get("sourceLanguage", None))
    target_language = check_is_language_valid(request.json_body.get("targetLanguage", None))
    translated_story = request.json_body.get("story", None)
    translated_oices = request.json_body.get("oices", None)

    if not target_language:
        raise ValidationError("ERR_INVALID_TARGET_LANGUAGE")

    translate_story(story, target_language, source_language, translated_story, translated_oices)

    return {
        'code': 200,
        'message': 'ok',
        'story': story.serialize(target_language),
    }


@story_translate.get(permission='get')
def get_translate(request):
    story = request.context

    source_language = story.language
    target_language = fetch_story_query_language(request, story)

    if not target_language:
        raise ValidationError("ERR_INVALID_TARGET_LANGUAGE")

    result = translate_story_preview(story, target_language, source_language)

    return {
        'code': 200,
        'message': 'ok',
        'result': result,
    }


@story_validate.get(permission='get')
def validate_story(request):
    story = request.context

    validator = ScriptValidator(story)
    return {
        'code': 200,
        'errors': validator.get_errors(),
        'storyErrors': validator.get_story_errors()
    }


@story_credits.get()
def get_story_credits(request):
    story_id = request.matchdict["story_id"]

    credits = get_story_credit(story_id)

    return {
        'message': 'ok',
        'code': 200,
        'credits': credits,
    }


@story_id_wordcount.get(permission='get')
def get_word_count_of_story(request):
    story = request.context
    query_language = fetch_story_query_language(request, story)

    return {
        'message': 'ok',
        'code': 200,
        "wordcount": count_words_of_block(DBSession, story=story, language=query_language),
    }


@story_build.get(permission='admin_set')
def build_story(request):
    story = request.context
    oices = story.published_oices
    batchId = uuid.uuid4().hex

    for oice in oices:
        view_url = get_oice_view_url(oice.uuid)
        oice_communication_url = get_oice_communication_url()
        og_image_button_url = oice.og_image_url_obj.get('button', '')
        og_image_origin_url = oice.image_url_obj.get('origin', '')
        worker = KSBuildWorker(oice.id, view_url, oice_communication_url, og_image_button_url, og_image_origin_url)
        worker.run(email="", isPreview=False, batchId=batchId)
    return {
        'message': 'ok',
        'batchId': batchId,
        'jobCount': len(oices)
    }


@story_like.post()
def like_story(request):
    user = UserQuery(DBSession).fetch_user_by_email(email=request.authenticated_userid).one_or_none()
    if not user:
        raise HTTPForbidden

    story = request.context

    if user not in story.liked_users:
        story.liked_users.append(user)
    else:
        raise ValidationError('ERR_STORY_LIKE_ALREADY')

    return {
        'code': 200,
        'message': 'ok',
    }


@story_like.delete()
def like_story(request):
    user = UserQuery(DBSession).fetch_user_by_email(email=request.authenticated_userid).one_or_none()
    if not user:
        raise HTTPForbidden

    story = request.context

    if user in story.liked_users:
        story.liked_users.remove(user)
    else:
        raise ValidationError('ERR_STORY_UNLIKE_ALREADY')

    return {
        'code': 200,
        'message': 'ok',
    }


@story_featured.get()
def get_featured_stories(request):
    # If there is no featured story in client language, return default language
    client_language = get_request_language(request)
    has_fs_in_client_language = FeaturedStoryQuery(DBSession).has_language(client_language)
    fs_language = client_language if has_fs_in_client_language else get_default_lang()

    limit = request.GET.get('limit', 20)

    featured_stories = FeaturedStoryQuery(DBSession).fetch_by_language(fs_language) \
                                                    .order_by(FeaturedStory.order) \
                                                    .limit(limit) \
                                                    .all()

    return {
        'code': 200,
        'message': 'ok',
        'stories': [fs.story.serialize_featured(language=fs_language) for fs in featured_stories],
    }


@tag_story.get()
def get_story_tag(request):
    client_language = get_request_language(request)

    return {
        'code': 200,
        'message': 'ok',
        'tags': [tag.serialize(language=client_language) for tag in StoryTagQuery(DBSession).fetch_all()],
    }


@app_story.get()
def get_app_story_list(request):
    user = get_request_user(request)
    client_language = get_request_language(request, user=user)

    filtered_story_ids = set()

    playing_story = None
    if 'playing_id' in request.GET:
        playing_story_id = request.GET['playing_id']
        try:
            playing_story = StoryQuery(DBSession).get_story_by_id(playing_story_id)
        except NoResultFound:
            pass
        else:
            filtered_story_ids.add(playing_story.id)

    has_fs_in_client_language = FeaturedStoryQuery(DBSession).has_language(client_language)
    fs_language = client_language if has_fs_in_client_language else get_default_lang()

    featured_stories = FeaturedStoryQuery(DBSession).fetch_by_language(fs_language) \
                                                    .order_by(FeaturedStory.order) \
                                                    .all()

    filtered_story_ids.update([fs.story_id for fs in featured_stories])

    before_time = datetime.datetime.utcnow()
    if 'before_time' in request.GET:
        try:
            timestamp = int(request.GET['before_time'])
            before_time = datetime.datetime.fromtimestamp(timestamp)
        except ValueError:
            pass
        except OverflowError:
            pass

    limit = request.GET.get('limit', 10)

    stories = StoryQuery(DBSession)\
        .get_stories_by_language(language=client_language,
                                 filtered_ids=filtered_story_ids,
                                 before_time=before_time)\
        .order_by(Story.updated_at.desc())\
        .limit(limit).all()

    return {
        'code': 200,
        'message': 'ok',
        'playingStory': playing_story.serialize_app(user, language=client_language) if playing_story else None,
        'featuredStories': [fs.story.serialize_app(user, language=fs_language) for fs in featured_stories],
        'localizedStories': [],  # Deprecated
        'stories': [s.serialize_app(user, language=client_language) for s in stories],
    }


@app_story_featured.get()
def get_app_featured_story(request):
    user = get_request_user(request)

    # If there is no featured story in client language, return story in default language
    client_language = get_request_language(request, user=user)
    has_fs_in_client_language = FeaturedStoryQuery(DBSession).has_language(client_language)
    fs_language = client_language if has_fs_in_client_language else get_default_lang()

    featured_stories = FeaturedStoryQuery(DBSession).fetch_by_language(fs_language) \
                                                    .order_by(FeaturedStory.tier, func.rand()) \
                                                    .all()

    return {
        'code': 200,
        'message': 'ok',
        'stories': [fs.story.serialize_app(user, language=fs_language) for fs in featured_stories],
    }


@app_story_v2.get()
def get_app_story_list_v2(request):
    user = get_request_user(request)

    # Language
    client_language = get_request_language(request, user=user)

    # Pagination
    before_time = datetime.datetime.utcnow()
    if 'before_time' in request.GET:
        try:
            timestamp = int(request.GET['before_time'])
            before_time = datetime.datetime.fromtimestamp(timestamp)
        except ValueError:
            pass
        except OverflowError:
            pass

    offset = request.GET.get('offset', 0)
    limit = request.GET.get('limit', 10)

    # Filter the stories (if any) from the story list
    filtered_story_ids = set(request.GET.get('filter', '').split(','))

    query = StoryQuery(DBSession).get_stories_by_language(language=client_language,
                                                          filtered_ids=filtered_story_ids,
                                                          before_time=before_time)

    # Tag
    if 'tag' in request.GET:
        tag_ids = request.GET['tag'].split(',')
        query = query.filter(and_(Story.tags.any(StoryTag.id == tag_id) for tag_id in tag_ids))

    stories = query \
        .order_by(
            Story.priority.desc() if 'offset' in request.GET else None,
            Story.updated_at.desc(),
        ) \
        .offset(offset) \
        .limit(limit) \
        .all()

    return {
        'code': 200,
        'message': 'ok',
        'stories': [s.serialize_app(user, language=client_language) for s in stories],
    }


@app_story_progress.get()
def get_app_story_progress(request):
    user = get_request_user(request)
    if not user:
        raise HTTPForbidden

    story = request.context
    query_language = normalize_language(request.GET.get('language'))

    # Get progress in last viewed ordering
    progress = UserReadOiceProgressQuery(DBSession).fetch_by_user_id_and_story(user.id, story) \
                                                   .filter(UserReadOiceProgress.is_finished)

    already_read_oice_ids = set(p.oice_id for p in progress)

    try:
        oice = next(o for o in story.published_oices if o.id not in already_read_oice_ids)
    except StopIteration:
        # Return last viewed oice if all oices have read and the last viewed oice is not the last episode
        # otherwise, return the first episode of the story instead
        oice = progress[0].oice if progress[0].oice.order != len(story.oice) - 1 else story.oice[0]

    return {
        'code': 200,
        'message': 'ok',
        'oice': oice.serialize(user, query_language),
    }


@app_story_id_episodes.get()
def get_app_story_episodes(request):
    story = request.context

    user = get_request_user(request)
    query_language = get_request_language(request, user=user)

    viewable_oice_ids = set()
    if user:
        progress = UserReadOiceProgressQuery(DBSession).fetch_by_user_id_and_story(user.id, story)
        already_read_oice_ids = set()

        for p in progress:
            viewable_oice_ids.add(p.oice_id)
            if p.is_finished:
                already_read_oice_ids.add(p.oice_id)

        # When user finished reading some episodes and haven't start the next episode
        if len(viewable_oice_ids - already_read_oice_ids) == 0:
            try:
                next_viewable_oice = next(o for o in story.published_oices if o.id not in viewable_oice_ids)
                viewable_oice_ids.add(next_viewable_oice.id)
            except StopIteration:
                pass

    return {
        'code': 200,
        'message': 'ok',
        'story': story.serialize_min(query_language),
        'oices': [
            {
                **o.serialize_profile(query_language),
                'viewable': o.id in viewable_oice_ids if viewable_oice_ids else False
            }
            for o in story.published_oices
        ],
    }
