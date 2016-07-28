# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import functools
import logging
import traceback

from builtins import str
from collections import namedtuple
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import mail_admins
from django.core.urlresolvers import reverse as urlreverse
from django.db import connection, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.core.mail import mail_managers
from requests.exceptions import ConnectionError

from edd.profile.models import UserProfile
from jbei.rest.auth import HmacAuth
from jbei.ice.rest.ice import parse_entry_id
from . import study_modified, user_modified
from ..models import (
    Line, MetaboliteExchange, MetaboliteSpecies, SBMLTemplate, Strain, Study, Update,
    UserPermission, GroupPermission, User, UNIT_TEST_FIXTURE_USERNAME)
from ..solr import StudySearch, UserSearch
from ..utilities import get_absolute_url


solr_study_index = StudySearch()
solr_users_index = UserSearch()
logger = logging.getLogger(__name__)

if settings.USE_CELERY:
    from edd.remote_tasks import link_ice_entry_to_study, unlink_ice_entry_from_study
else:
    from jbei.ice.rest.ice import IceApi

####################################################################################################
# Define custom signals
####################################################################################################


@receiver(post_save, sender=Study, dispatch_uid="main.signals.handlers.study_saved")
def study_saved(sender, instance, created, raw, using, **kwargs):
    if not raw and using == 'default':
        study_modified.send(sender=sender, study=instance)


@receiver(post_save, sender=get_user_model(), dispatch_uid="main.signals.handlers.user_saved")
def user_saved(sender, instance, created, raw, using, **kwargs):
    if not raw and using == 'default':
        user_modified.send(sender=sender, user=instance)


####################################################################################################
# Maintain study SOLR index based on changes to the study or related user/group permissions
####################################################################################################


@receiver(post_delete, sender=UserPermission,
          dispatch_uid=("%s.study_user_permission_post_delete" % __name__))
def study_user_permission_post_delete(sender, instance, using, **kwargs):
    logger.debug('Post-delete study permissions: %s' % str(instance.study.userpermission_set.all()))
    _schedule_post_commit_study_permission_index(instance)


@receiver(post_save, sender=UserPermission,
          dispatch_uid=("%s.study_user_permission_post_save" % __name__))
def study_user_permission_post_save(sender, instance, created, raw, using, **kwargs):
    logger.debug('Post-save study user permissions: %s' % str(instance.study.userpermission_set.all()))
    _schedule_post_commit_study_permission_index(instance)


@receiver(post_delete, sender=GroupPermission,
          dispatch_uid=("%s.study_group_permission_post_delete" % __name__))
def study_group_permission_post_delete(sender, instance, using, **kwargs):
    _schedule_post_commit_study_permission_index(instance)


@receiver(post_save, sender=GroupPermission,
          dispatch_uid=("%s.study_group_permission_post_save" % __name__))
def study_group_permission_post_save(sender, instance, created, raw, using, **kwargs):
    _schedule_post_commit_study_permission_index(instance)


def _schedule_post_commit_study_permission_index(study_permission):
    """
        Schedules a post-commit update of the SOLR index for the affected study whose permissions
        are affected
        """
    study = study_permission.study
    # package up work to be performed when the database change commits
    partial = functools.partial(_post_commit_index_study, study)
    # schedule the work for after the commit (or immediately if there's no transaction)
    connection.on_commit(partial)


@receiver(study_modified)
def index_study(sender, study, **kwargs):
    # return early if this change was triggered during a unit test
    if Update.is_unit_test_update():
        logger.info('Skipping solr updates for study pk=%(pk)s (name="%(name)s"). Changes were '
                    'detected to be part of a unit test.' % {
            'pk': str(study.pk),  # may be None!?
            'name': study.name,
        })
        return
    # package up work to be performed when the database change commits
    partial = functools.partial(_post_commit_index_study, study)
    # schedule the work for after the commit (or immediately if there's no transaction)
    connection.on_commit(partial)


def _post_commit_index_study(study):
    try:
        solr_study_index.update([study, ])
    except IOError:
        _handle_post_commit_function_error('Error updating Solr index for study %d' % study.pk)

PrimaryKeyCache = namedtuple('PrimaryKeyCache', ['id'])
"""
    Defines a cache for objects to-be-deleted so their primary keys can be available in post-commit
    hooks
"""


@receiver(pre_delete, sender=Study, dispatch_uid="main.signals.handlers.study_pre_delete")
def study_pre_delete(sender, instance, **kwargs):
    # package up work to be performed after the study is deleted / when the database change commits.
    # Note: we purposefully separate this from study_post_delete, since the study's primary key will
    # be removed from the Study object itself during deletion. Pre-delete is also too early to
    # perform the make changes since other issues may cause the deletion to fail.
    study = instance
    study.post_remove_pk_cache = PrimaryKeyCache(study.pk)


@receiver(post_delete, sender=Study, dispatch_uid="main.signals.handlers.study_post_delete")
def study_post_delete(sender, instance, **kwargs):
    # return early if this change was triggered during a unit test
    if Update.is_unit_test_update():
        logger.info('Skipping solr updates for study pk=%(pk)s (name="%(name)s"). Changes were '
                    'detected to be part of a unit test.' % {
                        'pk': str(study.pk),  # may be None!?
                        'name': study.name,
                    })
    # schedule the work for after the commit (or immediately if there's no transaction)
    study = instance
    partial = functools.partial(_post_commit_unindex_study, study.post_remove_pk_cache)
    connection.on_commit(partial)


def _post_commit_unindex_study(study_pk):
    try:
        solr_study_index.remove([study_pk, ])
    except IOError:
        _handle_post_commit_function_error('Error updating Solr index for study %d' % study_pk)


####################################################################################################
# Index user
####################################################################################################
@receiver(user_modified)
def index_user(sender, user, **kwargs):
    # package up work to be performed when the database change commits
    partial = functools.partial(_post_commit_index_user, user)
    # schedule the work for after the commit (or immediately if there's no transaction)
    connection.on_commit(partial)


def _post_commit_index_user(user):
        try:
            solr_users_index.update([user, ])
        # catch Solr/connection errors that occur during the user login process / email admins
        # regarding the error. users may not be able to do much without Solr, but they can still
        # access existing studies (provided the URL), and create new ones. Solr being down
        # shouldn't prevent the login process (EDD-201)
        except IOError as e:
            _handle_post_commit_function_error("Error updating Solr with user information for "
                                               "user %s" % user.username)


@receiver(pre_delete, sender=get_user_model(),
          dispatch_uid="main.signals.handlers.user_pre_delete")
def user_pre_delete(sender, instance, using, **kwargs):
    # cache the user's primary key for use in post_delete, which will be removed from the User
    # object itself during deletion
    user = instance
    user.post_remove_pk_cache = PrimaryKeyCache(instance.pk)


@receiver(post_delete, sender=get_user_model(), dispatch_uid=("%s.user_post_delete" % __name__))
def user_post_delete(sender, instance, using, **kwargs):
    user = instance
    logger.info('Start of user_post_delete(): username=%s' % instance.username)

    # get the user pk we cached in pre_delete (pk data member gets removed during the deletion)
    post_remove_pk_cache = user.post_remove_pk_cache

    # schedule the Solr update for after the commit (or immediately if there's no transaction)
    partial = functools.partial(_post_commit_unindex_user, post_remove_pk_cache)
    connection.on_commit(partial)


def _post_commit_unindex_user(user_pk_cache):
    try:
        solr_users_index.remove([user_pk_cache, ])
    except IOError:
        _handle_post_commit_function_error(
                'Error updating Solr index for user %d' % user_pk_cache.id)

####################################################################################################


def log_update_warning_msg(study_id):
    logger.warning('ICE URL is not configured. Skipping attempt to link ICE parts to EDD study "%s"'
                   % study_id)


@receiver(pre_save, sender=Study, dispatch_uid="main.signals.handlers.handle_study_pre_save")
def handle_study_pre_save(sender, instance, raw, using, **kwargs):
    if not settings.ICE_URL:
        logger.warning('ICE URL is not configured. Skipping ICE experiment link updates.')
        return
    elif raw:
        return

    # if the study was already saved, cache its name as stored in the database so we can detect
    # renaming
    if instance.pk:
        instance.pre_save_name = Study.objects.filter(pk=instance.pk).values('name')[0]['name']
    # if the study is new
    else:
        instance.pre_save_name = None


@receiver(post_save, sender=Study, dispatch_uid="main.signals.handlers.handle_study_post_save")
def handle_study_post_save(sender, instance, created, raw, using, **kwargs):
    """
    Checks whether the study has been renamed by comparing its current name with the one set in
    handle_study_pre_save. If it has, and if the study is associated with any ICE strains, updates
    the corresponding ICE entry(ies) to label links to this study with its new name.
    """
    if not settings.ICE_URL:
        logger.warning('ICE URL is not configured. Skipping ICE experiment link updates.')
        return
    elif raw:
        return

    logger.info("Start " + handle_study_post_save.__name__ + "()")

    study = instance

    if study.name == study.pre_save_name:
        return

    logger.info('Study "%s" has been renamed to "%s"' % (study.pre_save_name, study.name))

    # get the strains associated with this study so we can update link name for the corresponding
    # ICE entries (if any). note that this query only returns ONE row for the strain,
    # even if it's linked to multiple EDD studies. ICE will update ALL links to this study URL
    # for every part that references it, so we don't need to launch a separate Celery task for
    # each. See comments on SYNBIO-1196.
    strains = Strain.objects.filter(line__study_id=study.pk).prefetch_related('created')

    if strains:
        update = Update.load_update()  # find which user made the update that caused this signal
        user_email = update.mod_by.email

        # filter out strains that don't have enough information to link to ICE
        strains_to_link = []
        for strain in strains.all():
            if not _is_linkable(strain):
                logger.warning(
                    "Strain with id %d is no longer linked to study id %d, but doesn't have "
                    "enough data to link to ICE. It's possible (though unlikely) that the EDD "
                    "strain has been modified since an ICE link was created for it."
                    % (strain.pk, study.pk))
                continue
            strains_to_link.append(strain)
        # schedule ICE updates as soon as the database changes commit
        partial = functools.partial(_post_commit_link_ice_entry_to_study, user_email, study,
                                                                          strains_to_link)
        connection.on_commit(partial)
        logger.info("Scheduled post-commit work to update labels for %d of %d strains "
                    "associated with study %d"
                    % (len(strains_to_link), strains.count(), study.pk))


@receiver(pre_delete, sender=Line, dispatch_uid="main.signals.handlers.handle_line_pre_delete")
@transaction.atomic(savepoint=False)
def handle_line_pre_delete(sender, instance, **kwargs):
    """
    Caches study <-> strain associations prior to deletion of a line and/or study so we can remove
    a study link from ICE if needed during post_delete.
    """
    logger.debug("Start %s()" % handle_line_pre_delete.__name__)

    if not settings.ICE_URL:
        logger.warning('ICE URL is not configured. Skipping ICE experiment link updates.')
        return

    line = instance
    with transaction.atomic():
        instance.pre_delete_study_id = line.study.pk
        instance.pre_delete_study_timestamp = line.study.created.mod_time
        instance.pre_delete_strains = Strain.objects.filter(line__id=line.pk)

        # force query evaluation now instead of when we read the result
        len(instance.pre_delete_strains)


@receiver(post_delete, sender=Line, dispatch_uid="main.signals.handlers.handle_line_post_delete")
@transaction.atomic(savepoint=False)
def handle_line_post_delete(sender, instance, **kwargs):
    """
    Checks study <-> strain associations following line deletion and removes study links from ICE
    for any strains that are no longer associated with the study. Note that the m2m_changed
    signal isn't broadcast when lines or studies are deleted. This signal is broadcast is in both
    cases, so we'll use it to fill the gap.
    """
    logger.debug("Start " + handle_line_post_delete.__name__ + "()")

    if not settings.ICE_URL:
        logger.warning('ICE URL is not configured. Skipping ICE experiment link updates.')
        return

    line = instance

    # extract study-related data cached prior to the line deletion. Note that line deletion signals
    # are also sent during/after study deletion, so this information may not be in the database
    # any more
    study_pk = line.pre_delete_study_id
    study_creation_datetime = line.pre_delete_study_timestamp

    # build a list of strains that are no longer associated with this study due to deletion of
    # the line.
    post_delete_strain_ids = [strain.pk for strain in
                              Strain.objects.filter(line__study_id=study_pk).all()]
    removed_strains = [strain for strain in line.pre_delete_strains if
                       strain.pk not in post_delete_strain_ids]

    logger.debug("pre_delete_strain_ids: %s" % instance.pre_delete_strains)
    logger.debug("post-delete_strain_ids: %s" % post_delete_strain_ids)
    logger.debug("removed_strain_ids: %s" % removed_strains)

    # find which user made the update that caused this signal
    update = Update.load_update()

    if not (update and update.mod_by and update.mod_by.email):
        username = update.mod_by.username if (update and update.mod_by) else 'Unknown user'
        msg = ('No user email could be found associated with the in-progress deletion of '
               'line %(line_pk)d "%(line_name)s by user "%(username)s". Line deletion will '
               'proceed,  but the associated experiment link in ICE will remain in place because '
               'a user identity is required to update experiment links in  ICE. Please manually '
               'delete this link using the ICE user interface.\n'
               'This situation is known to occur when a line is deleted directly from the Django '
               'shell rather than from the EDD user interface. ' % {
                    'line_pk': line.pk,
                    'line_name': line.name,
                    'username': username
                })
        subject = "Stale ICE experiment link won't be deleted"
        logger.warning(subject)
        logger.warning(msg)
        mail_admins(subject, msg)
        return

    user_email = update.mod_by.email
    logger.debug("update performed by user " + user_email)

    # wait until the connection commits, then schedule a Celery task to remove the link from ICE.
    # Note that if we don't wait, the Celery task can run before it commits, at which point its
    # initial DB query
    # will indicate an inconsistent database state. This happened repeatably during testing.
    partial = functools.partial(_post_commit_unlink_ice_entry_from_study, user_email, study_pk,
                                study_creation_datetime, removed_strains)
    connection.on_commit(partial)


def _post_commit_unlink_ice_entry_from_study(user_email, study_pk, study_creation_datetime,
                                             removed_strains):
    """
    Helper method to do the final work in scheduling a Celery task or ICE REST API call to remove
    a link from ICE AFTER the database transaction that implements the EDD portion of the linking
    has committed. This method is only strictly necessary to help us work around the
    django-commit-hooks limitation that a no-arg method be passed to the post-commit hook.
    """
    logger.info('Start ' + _post_commit_unlink_ice_entry_from_study.__name__ + '()')

    ice = None
    if not settings.USE_CELERY:
        ice = IceApi(auth=HmacAuth(key_id=settings.ICE_KEY_ID, username=user_email))

    study_url = get_abs_study_url(study_pk)
    index = 0

    try:
        # loop over strain data cached prior to line deletion. note that the strains themselves
        # may have been deleted at this point, so safest to use cached data instead
        # Note: even though only a single line was deleted, possible it links to multiple strains
        change_count = 0
        for strain in removed_strains:

            # print a warning and skip any strains that didn't include enough data for a link to ICE
            if not _is_linkable(strain):
                logger.warning(
                    "Strain with id %d is no longer linked to study id %d, but EDD's "
                    "database entry for this strain doesn't have enough data to remove the "
                    "corresponding study link from ICE. It's possible (though unlikely) that the "
                    "EDD strain has been modified since an ICE link was created for it." %
                    (strain.pk, study_pk)
                )
                index += 1
                continue

            # as a workaround for SYNBIO-1207, prefer the ICE id extracted from the URL,
            # which is much more likely to be the locally-unique numeric ID visible from the ICE
            # UI. Not certain  what recent EDD changes have done to new strain creation, but at
            # least some pre-existing strains  will work better with this method
            # TODO: after removing the workaround, use, ice_strain_id =
            # strain.registry_id.__str__(), or if using Python 3,
            # maybe strain.registry_id.to_python(). Note that the JSON lib has no  built-in support
            # for UUIDs
            workaround_strain_id = parse_entry_id(strain.registry_url)

            if settings.USE_CELERY:
                async_result = unlink_ice_entry_from_study.delay(user_email, study_pk, study_url,
                                                                 strain.registry_url,
                                                                 workaround_strain_id)
                track_celery_task_submission(async_result)
            else:
                ice.write_enabled = True
                ice.unlink_entry_from_study(workaround_strain_id, study_pk, study_url, logger)
            change_count += 1
            index += 1

        if settings.USE_CELERY:
            logger.info("Submitted %d jobs to Celery" % change_count)
        else:
            logger.info("Updated %d links via direct HTTP requests" % change_count)

    # if an error occurs, print a helpful log message, then re-raise it so Django will email
    # administrators
    except Exception as err:
        strain_pks = [strain.pk for strain in removed_strains]
        _handle_ice_post_commit_error(err, 'remove', study_pk, strain_pks, index)


def _post_commit_link_ice_entry_to_study(user_email, study, linked_strains):
    """
    Helper method to do the final work in scheduling a Celery task or ICE REST API call to add a
    link from ICE AFTER the database transaction that implements the EDD portion of the linking
    has committed. This method is only strictly necessary to help us work around the
    django-commit-hooks limitation that a no-arg method be passed to the post-commit hook.
    :param linked_strains cached strain information
    """
    ice = None
    if not settings.USE_CELERY:
        ice = IceApi(auth=HmacAuth(key_id=settings.ICE_KEY_ID, username=user_email))

    index = 0

    try:
        study_url = get_abs_study_url(study.pk)

        # loop over strains and perform / schedule work needed
        for strain in linked_strains:
            # If Celery is configured, use it to perform the communication with ICE,
            # along with retries/failure notifications, etc.
            if settings.USE_CELERY:
                async_result = link_ice_entry_to_study.delay(user_email, strain.pk, study.pk,
                                                             study_url)
                track_celery_task_submission(async_result)
            # Otherwise, communicate with ICE synchronously during signal processing
            else:
                logger.warning(
                    "Celery configuration not found. Attempting to push study links directly ("
                    "retries, admin notifications not supported)")
                #  as a workaround for SYNBIO-1207, prefer the ICE id extracted from the URL,
                # which is much more likely to be the locally-unique numeric ID visible from the
                # ICE UI. Not certain what recent EDD changes have done to new strain creation,
                # but at least some pre-existing strains will work better with this method.
                # TODO: after removing the workaround, use, ice_strain_id =
                # strain.registry_id.__str__(), or if using Python 3,
                # maybe strain.registry_id.to_python()
                workaround_strain_id = parse_entry_id(strain.registry_url)
                ice.write_enabled = True
                ice.link_entry_to_study(workaround_strain_id, study.pk, study_url, study.name,
                                        logger)

            index += 1

    # if an error occurs, print a helpful log message, then re-raise it so Django will email
    # administrators
    except Exception as err:
        linked_strain_pks = [strain.pk for strain in linked_strains]
        _handle_ice_post_commit_error(err, 'add/update', study.pk, linked_strain_pks, index)


def _handle_ice_post_commit_error(err, operation, study_pk, strains_to_update, index):
    """
    Handles exceptions from post-commit functions used to communicate with ICE. Note that although
    Django typically automatically handles uncaught exceptions by emailing admins, it doesn't seem
    to be handling them in the case of post-commit functions/lambda's (see EDD-178)
    :param err:
    :return:
    """
    error_msg = None
    if settings.USE_CELERY:
        error_msg = ("Error submitting Celery jobs to %(operation)s ICE strain link(s) for study "
                     "%(study_pk)d. Strains to update: %(strains)s (index=%(index)d)" % {
                        'operation': operation,
                        'study_pk': study_pk,
                        'strains': str(strains_to_update),
                        'index': index, })
    else:
        error_msg = "Error updating ICE links via direct HTTP request (index=%d)" % index

    _handle_post_commit_function_error(error_msg)


def _handle_post_commit_function_error(err_msg, re_raise_error=None):
    """
        A workaround for EDD-176: Django doesn't seem to be picking up errors / emailing admins
        for uncaught exceptions in post-commit signal handler functions.
        Note that even if Django
        resolves this we *still* often won't want to raise the exception since that would cause
        the EDD user to get an error message for a process that from their perspective was a
        partial/total success. For ICE messaging tasks, we can consider changing this behavior
        after  deploying Celery in production (EDD-176), which will effectively mask ICE
        communication / integration errors from EDD users since they'll occur outside the context
        of the browser's request. At that point, errors generated here will just reflect errors
        communicating with Celery, which should probably still be masked from users.
        :param err_msg: a brief string description of the error that will get logged / emailed to
        admins
        :param re_raise_error: a reference to the Error/Exception that was thrown if it should be
        re-raised after being logged / emailed to admins. Often this should only be done if the
        error is severe enough that it justifies interrupting the users current workflow. Note that
        a traceback will be logged / emailed even if this parameter isn't included.
    """

    logger.exception(err_msg)  # Note: purposeful to not pass the error here! Often the cause of
                               # unicode exceptions! See SYNBIO-1267.
    traceback_str = build_traceback_msg()
    msg = '%s\n\n%s' % (err_msg, traceback_str)
    mail_admins(err_msg, msg)

    if re_raise_error:
        raise re_raise_error


def _is_linkable(strain):
    return _is_strain_linkable(strain.registry_url, strain.registry_id)


def _is_strain_linkable(registry_url, registry_id):
    #  as a workaround for SYNBIO-1207, we'll extract the ICE part ID from the URL to increase
    # the odds that it'll be a numeric ID that won't cause 404 errors. otherwise, we could just
    # construct the URL from the registry ID and our ICE configuration data
    return registry_url and registry_id


@receiver(m2m_changed, sender=Line.strains.through, dispatch_uid=("%s.handle_line_strain_changed"
                                                                  % __name__))
@transaction.atomic(savepoint=False)
def handle_line_strain_changed(sender, instance, action, reverse, model, pk_set, using, **kwargs):
    """
    Handles changes to the Line <-> Strain relationship caused by adding/removing/changing the
    strain associated with a single line in a study. Detects changes that indicate a need to push
    changes across to ICE for the (ICE part -> EDD study) link stored in ICE.
    """

    # ignore calls that indicate a change from the perspective of the model data member we don't
    # presently have implemented. Even if the data member is added later, we don't want to
    # process the same strain/line link twice from both perspectives...
    # it's currently Line that links back to Study and impacts which data we want to push to ICE.
    log_format = {
        'method': handle_line_strain_changed.__name__,
        'action': action,
        'name': instance.name,
        'reverse': reverse,
        'pk_set': pk_set,
    }
    if reverse:
        logger.info(
            'Start %(method)s():%(action)s. Strain = "%(name)s", reverse = %(reverse)s, '
            'pk_set = %(pk_set)s' % log_format
        )
        return

    logger.info(
        'Start %(method)s():%(action)s. Line = "%(name)s", reverse = %(reverse)s, '
        'pk_set = %(pk_set)s' % log_format
    )

    if not settings.ICE_URL:
        logger.warning('ICE URL is not configured. Skipping ICE experiment link updates.')
        return

    line = instance  # just call it a line for clarity now that we've verified that it is one

    # find which user made the update that caused this signal
    update = Update.load_update()
    if update.mod_by and (update.mod_by.username == UNIT_TEST_FIXTURE_USERNAME):
        logger.warning("Detected line/strain relationship changes that originated from "
                       "unit test code. Skipping ICE notifications.")
        return

    # detect changes made by improper unit test configuration and/or another integration error
    if update.mod_by is None:
        logger.error("Detected improper unit test configuration or another integration "
                     "error. Unable to attribute line/strain relationship changes to a "
                     "user, so ICE notifications that require a username will be skipped. "
                     "As a result, manual curation of ICE link(s) for be required for "
                     "study with pk %d" % line.study_id)
        return

    user_email = update.mod_by.email
    logger.debug("update performed by user " + user_email)

    if "pre_clear" == action:
        # save contents of the relation before Django clears it in preparation to re-add
        # everything (including new items). This is the (seemingly very
        # inefficient/inconvenient/misleading) process Django uses each time, regardless of the
        # number of adds/removals actually taking place. ordinarily assuming that a "clear"
        # operation always precedes an "add" would be problematic, but it appears safe in this
        # case since the only time the M2M relationship between Lines / Strains should ever be
        # cleared is either when a study is deleted, or as an intermediate step by Django during
        # the save process. Seems like a very inefficient way of doing it, but improving that
        # behavior is out-of-scope for us here.

        # NOTE: call to list() forces query evaluation here rather than when we read the result
        # in post_add
        line.pre_clear_strain_pks = list(line.strains.values_list('pk', flat=True))
        return

    elif "post_add" == action:
        added_strains = list(line.strains.filter(pk__in=pk_set))
        logger.debug("added_strains = %s" % str(added_strains))

        # schedule asynchronous work to maintain ICE strain links to this study, failing if any
        # job submission fails (probably because our link to Celery or RabbitMQ is down, and isn't
        # likely to come back up for subsequently attempted task submissions in the loop)
        study = line.study

        strain_pk = 0
        try:

            add_on_commit_strains = []
            for strain in added_strains:
                strain_pk = strain.pk

                # skip any strains that aren't associated with an ICE entry
                if not _is_linkable(strain):
                    logger.warning(
                        "Strain with id %d is now linked to study id %d, but EDD's "
                        "database entry for the strain doesn't contain enough data to create an "
                        "ICE link back to the study. It's possible (though unlikely) that the "
                        "EDD strain has been modified since an ICE link was created for it."
                        % (strain.pk, study.pk))
                    continue

                add_on_commit_strains.append(strain)

            if add_on_commit_strains:
                # wait until the connection commits, then schedule work to add/update the link(s)
                # in ICE. Note that if we don't wait, the Celery task can run before it commits,
                # at which point its initial DB query will indicate an inconsistent database
                # state. This happened repeatably during testing.
                partial = functools.partial(_post_commit_link_ice_entry_to_study, user_email, study,
                                            add_on_commit_strains)
                connection.on_commit(partial)

            exp_add_count = len(pk_set)
            linkable_count = len(add_on_commit_strains)

            if settings.USE_CELERY:
                logger.info("Done scheduling post-commit work to submit jobs to Celery: will "
                            "submit ICE link creation task for each %d of %d added strains." %
                            (linkable_count, exp_add_count))
            else:
                logger.info(
                    "Done scheduling post-commit work for direct HTTP request(s) to ICE: "
                    "requested a job to sequentially create links for %d of %d added "
                    "strains via direct HTTP request(s)." % (linkable_count, exp_add_count))

        # if an error occurs, print a helpful log message, then re-raise it so Django will email
        # administrators
        except Exception:
            logger.exception("Exception scheduling post-commit work. Failed on strain with id %d" %
                             strain_pk)
    elif 'pre_remove' == action:
        # cache data associated with this strain so we have enough info to remove some or all of
        # ICE's link(s) to this study if appropriate after line -> strain relationship change is
        # completed in EDD
        line.removed_strains = Strain.objects.filter(pk__in=pk_set)
    elif 'post_remove' == action:
        removed_strains = line.removed_strains
        logger.debug("removed_strains = %s" % (removed_strains, ))


        # schedule asynchronous work to maintain ICE strain links to this study, failing if any
        # job submission fails (probably because our link to Celery or RabbitMQ is down, and
        # isn't likely to come back up for subsequently attempted task submissions in the loop)
        study = line.study
        strain_pk = 0

        try:

            # narrow down the list of lines that are no longer associated with this strain to
            # just those
            # we want to take action on in ICE.
            remove_on_commit = []
            for strain in removed_strains:
                strain_pk = strain.pk
                # skip any strains that can't be associated with an ICE entry
                if not _is_linkable(strain):
                    logger.warning(
                        "Strain with id %d is no longer linked to study id %d, but EDD's "
                        "database entry for the strain doesn't have enough data to facilitate "
                        "removal of the corresponding study link from ICE (if any).  It's "
                        "possible, though unlikely, that the EDD strain has been modified "
                        "since an ICE link was created for it."
                        % (strain.pk, study.pk))
                    continue
                # test whether any lines still exist that link the study to this strain. if not,
                # schedule a task to remove the link from ICE. Note that we could skip this check
                # and just depend on the one in unlink_ice_part_from_study, but that would remove
                # our ability to detect stale tasks in the pipeline
                lines = Line.objects.filter(strains__registry_url=strain.registry_url,
                                            study__pk=study.pk,
                                            study__created__mod_time=study.created.mod_time)
                if lines:
                    logger.warning(
                        "Found %d other lines linking study id %d to strain id %d. The ICE link "
                        "to this study won't be removed." % (lines.count(), study.pk, strain.pk))
                    continue
                remove_on_commit.append(strain)

            if remove_on_commit:
                # wait until the transaction commits, then schedule work to remove the link(s)
                # from ICE. Note that if we don't wait, the Celery task can run before it commits,
                # at which point its initial DB query will indicate an inconsistent database
                # state. This happened repeatably during testing.
                partial = functools.partial(_post_commit_unlink_ice_entry_from_study,user_email,
                                            study.pk, study.created.mod_time, remove_on_commit)
                connection.on_commit(partial)
        except ChangeFromFixture:
            logger.warning("Detected changes from fixtures, skipping ICE signal handling.")
        # if an error occurs, print a helpful log message, then re-raise it so Django will email
        # administrators
        except Exception:
            logger.exception("Exception scheduling post-commit work. Failed on strain with id %d" %
                             strain_pk)

    logger.debug("End " + handle_line_strain_changed.__name__ + "():" + action)


def get_abs_study_url(study_pk):
    # Note: urlreverse is an alias for reverse() to avoid conflict with named parameter
    study_relative_url = urlreverse('main:detail', kwargs={'pk': study_pk})
    return get_absolute_url(study_relative_url)


def track_celery_task_submission(async_result):
    """
    A placeholder method for tracking Celery task submission (see SYNBIO-1204.). An unlikely,
    but reproducible failure mode observed during initial testing was that for a few seconds
    following RabbitMQ being stopped while Celery runs, tasks submitted during that window will
    be perpetually in the "Pending" state. Even once Rabbit is restarted, the tasks will remain
    in that state without ever generating a client-side exception or any other failure
    notification. To improve EDD's ability to these detect errors, we should implement some
    tracking here to catch such cases. For example, we might keep a list of submitted Celery
    tasks that we periodically scan on a background thread and generate warning emails if any old
    tasks are unexpectedly in the "Pending" state.

    TODO: confirm that no database entry is created for tasks in this scenario either. It's been a
    long time since this test was performed.
    :param async_result:
    """
    logger.warning("TODO: track status of tasks submitted to the Celery library, but maybe not yet "
                   "communicated to the server (SYNBIO-1204)")


@receiver(post_save, sender=SBMLTemplate)
def template_saved(sender, instance, created, raw, using, update_fields, **kwargs):
    if not raw and (created or update_fields is None or 'sbml_file' in update_fields):
        # TODO: add celery task for template_sync_species
        template_sync_species(instance)


def template_sync_species(instance):
    doc = instance.parseSBML()
    model = doc.getModel()
    # filter to only those for the updated template
    species_qs = MetaboliteSpecies.objects.filter(sbml_template=instance)
    exchange_qs = MetaboliteExchange.objects.filter(sbml_template=instance)
    # values_list yields a listing of tuples, unwrap the value we want
    exist_species = {s[0] for s in species_qs.values_list('species')}
    exist_exchange = {r[0] for r in exchange_qs.values_list('exchange_name')}
    # creating any records not in the database
    for species in map(lambda s: s.getId(), model.getListOfSpecies()):
        if species not in exist_species:
            MetaboliteSpecies.objects.get_or_create(sbml_template=instance, species=species)
        else:
            exist_species.remove(species)
    reactions = map(lambda r: (r.getId(), r.getListOfReactants()), model.getListOfReactions())
    for reaction, reactants in reactions:
        if len(reactants) == 1 and reaction not in exist_exchange:
            MetaboliteExchange.objects.get_or_create(
                sbml_template=instance,
                exchange_name=reaction,
                reactant_name=reactants[0].getSpecies()
            )
        else:
            exist_exchange.remove(reaction)
    # removing any records in the database not in the template document
    species_qs.filter(species__in=exist_species).delete()
    exchange_qs.filter(exchange_name__in=exist_exchange).delete()


def build_traceback_msg():
    """
    Builds an error message for inclusion into an email to sysadmins
    :return:
    """
    formatted_lines = traceback.format_exc().splitlines()
    traceback_str = '\n'.join(formatted_lines)
    return 'The contents of the full traceback was:\n\n%s' % traceback_str
