"""
Unit tests for EDD's REST API.

Tests in this module operate directly on the REST API itself, on and its HTTP responses, and
purposefully don't use Python API client code in jbei.rest.clients.edd.api. This focus on unit
testing of REST API resources enables finer-grained checks, e.g. for permissions /
security and for HTTP return codes that should verified independently of any specific client.

Note that tests here purposefully hard-code simple object serialization that's also coded
seperately in EDD's REST API.  This should help to detect when REST API code changes in EDD
accidentally affect client code.
"""
from __future__ import unicode_literals
import json
import logging
from pprint import pformat
from uuid import UUID

import collections
from django.conf import settings
from django.contrib.auth.models import Permission, Group
from rest_framework.status import (HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST,
                                   HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND,
                                   HTTP_405_METHOD_NOT_ALLOWED)
from rest_framework.test import APITestCase

from jbei.rest.clients.edd.constants import (STRAINS_RESOURCE_NAME, STRAIN_DESCRIPTION_KEY,
                                             STRAIN_NAME_KEY, STRAIN_REG_ID_KEY,
                                             STRAIN_REG_URL_KEY, NEXT_PAGE_KEY, PREVIOUS_PAGE_KEY,
                                             RESULT_COUNT_KEY, RESULTS_KEY, STUDIES_RESOURCE_NAME,
                                             STUDY_DESCRIPTION_KEY, STUDY_NAME_KEY, UUID_KEY)
from main.models import (Line, Strain, Study, StudyPermission, User, GroupPermission,
                         UserPermission, EveryonePermission)

logger = logging.getLogger(__name__)

SEPARATOR = '*' * 40

# See
# http://www.django-rest-framework.org/api-guide/authentication/#unauthorized-and-forbidden-responses
DRF_UNAUTHENTICATED_PERMISSION_DENIED_CODES = (HTTP_403_FORBIDDEN, HTTP_401_UNAUTHORIZED)

# status code always returned by Django REST Framework when a successfully
# authenticated request is denied permission to a resource.
# See http://www.django-rest-framework.org/api-guide/authentication/#unauthorized-and-forbidden
# -responses
DRF_AUTHENTICATED_BUT_DENIED = HTTP_403_FORBIDDEN

UNPRIVILEGED_USERNAME = 'unprivileged_user'
STAFF_USERNAME = 'staff.user'
STAFF_STUDY_USERNAME = 'staff.study.user'
ADMIN_USERNAME = 'admin.user'
ADMIN_STAFF_USERNAME = 'admin.staff.user'

STUDY_OWNER_USERNAME = 'unprivileged.study.owner'
STUDY_READER_USERNAME = 'study.reader.user'
STUDY_READER_GROUP_USER = 'study.reader.group.user'
STUDY_READER_GROUP_NAME = 'study_readers'
STUDY_WRITER_GROUP_USER = 'study.writer.group.user'
STUDY_WRITER_USERNAME = 'study.writer.user'

# Note: ApiTestCase runs in a transction that aborts at the end of the test, so this password will
# never be externally exposed.
PLAINTEXT_TEMP_USER_PASSWORD = 'password'

STRAINS_RESOURCE_URL = '/rest/%(resource)s' % {'resource': STRAINS_RESOURCE_NAME}
STUDIES_RESOURCE_URL = '/rest/%(resource)s' % {'resource': STUDIES_RESOURCE_NAME}

DRF_UPDATE_ACTION = 'update'
DRF_CREATE_ACTION = 'create'
DRF_LIST_ACTION = 'list'
DRF_DELETE_ACTION = 'delete'

# Note: some uses have an iterable of expected statuses...hence string format
_WRONG_STATUS_MSG = ('Wrong response status code from %(method)s %(url)s for user %(user)s. '
                     'Expected %(expected)s status but got %(observed)d')


class MyApiTestCase(APITestCase):
    """
    Overrides APITestCase to provide helper methods that improve test error messages and simplify
    client code.
    """
    def _require_unauthenticated_put_denied(self, url, put_data):
        self.client.logout()
        response = self.client.put(url, put_data)
        self.assertTrue(response.status_code in DRF_UNAUTHENTICATED_PERMISSION_DENIED_CODES)

    def _require_unauthenticated_get_denied(self, url):
        self.client.logout()
        response = self.client.get(url)
        self.assertTrue(response.status_code in DRF_UNAUTHENTICATED_PERMISSION_DENIED_CODES)

    def _require_unauthenticated_delete_denied(self, url):
        self.client.logout()
        response = self.client.delete(url)
        self.assertTrue(response.status_code in DRF_UNAUTHENTICATED_PERMISSION_DENIED_CODES)

    def _require_unauthenticated_post_denied(self, url, post_data):
        self.client.logout()
        response = self.client.post(url, post_data, format='json')
        self.assertTrue(response.status_code in DRF_UNAUTHENTICATED_PERMISSION_DENIED_CODES,
                        (_WRONG_STATUS_MSG + 'response was %(response)s') % {
                            'method':   'POST', 'url': url,
                            'user':     'unauthenticated',
                            'expected': str(DRF_UNAUTHENTICATED_PERMISSION_DENIED_CODES),
                            'observed': response.status_code,
                            'response': str(response)})

    def _require_authenticated_post_denied(self, url, user, post_data):
        self._do_post(url, user, post_data, HTTP_403_FORBIDDEN)

    def _require_authenticated_put_denied(self, url, user, post_data):
        self._do_put(url, user, post_data, HTTP_403_FORBIDDEN)

    def _require_authenticated_post_allowed(self, url, user, post_data,
                                            required_response=None,
                                            partial_response=False):
        return self._do_post(url, user, post_data, HTTP_201_CREATED, required_response,
                             partial_response)

    def _require_authenticated_put_allowed(self, url, user, post_data):
        self._do_put(url, user, post_data, HTTP_200_OK)

    def _require_authenticated_post_conflict(self, url, user, post_data):
        self._do_post(url, user, post_data, HTTP_400_BAD_REQUEST)

    def _do_post(self, url, user, post_data, required_status, required_response_dict=None,
                 partial_response=False):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)
        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.post(url, post_data, format='json')
        self.client.logout()

        self.assertEquals(required_status, response.status_code,
                          (_WRONG_STATUS_MSG + 'response was %(response)s') % {
                              'method': 'POST',
                              'url':      url, 'user': user.username,
                              'expected': required_status,
                              'observed': response.status_code,
                              'response': str(response),
                          })

        if required_response_dict:
            print("Response: %s" % response.content)  # TODO: remove debug stmt
            observed_response_dict = json.loads(response.content)
            if not partial_response:
                self.assertEqual(required_response_dict, observed_response_dict)
            else:
                for key, required_value in required_response_dict.iteritems():
                    observed_value = observed_response_dict[key]
                    self.assertEqual(required_value, observed_value)

        return response

    def _do_put(self, url, user, put_data, required_status):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)
        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')
        response = self.client.put(url, put_data, format='json')
        self.client.logout()

        self.assertEquals(required_status, response.status_code,
                          _WRONG_STATUS_MSG % {
                              'method': 'PUT',
                              'url':      url,
                              'user': user.username,
                              'expected': required_status,
                              'observed': response.status_code
                          })

    def _require_authenticated_get_denied(self, url, user):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)
        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.get(url)
        expected_status = HTTP_404_NOT_FOUND

        self.assertEquals(expected_status,
                          response.status_code,
                          (_WRONG_STATUS_MSG  + '. Response: %(result)s') % {
                              'method': 'GET',
                              'url': url,
                              'user': user.username,
                              'expected': expected_status,
                              'observed': response.status_code,
                              'result': response.content})
        self.client.logout()

    def _require_authenticated_get_allowed(self, url, user, expected_values=None,
                                           values_converter=None, partial_response=False):
        self._do_get(url, user, HTTP_200_OK, expected_values, values_converter,
                     partial_response=partial_response)

    def _do_get(self, url, user, expected_status, expected_values=None, values_converter=None,
                partial_response=False):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)
        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.get(url)
        self.assertEquals(expected_status, response.status_code, _WRONG_STATUS_MSG % {
            'method':   'GET',
            'url': url,
            'user': user.username,
            'expected': expected_status,
            'observed': response.status_code
        })

        if expected_values is not None:
            expected = to_json_comparable_dict(expected_values, values_converter)
            observed = json.loads(response.content)

            if isinstance(expected_values, collections.Iterable):
                compare_paged_result_dict(self, expected, observed, order_agnostic=True,
                                          partial_response=partial_response)
            else:
                if not partial_response:
                    self.assertEqual(expected, observed,
                                     "Query contents didn't match expected values.\n\n"
                                     "Expected: %(expected)s\n\n"
                                     "Observed:%(observed)s" % {
                                         'expected': expected,
                                         'observed': observed,
                                     })
                else:
                    _compare_partial_value(self, expected, observed)
        self.client.logout()

    def _do_delete(self, url, user, expected_status):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)
        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.delete(url)
        self.assertEquals(expected_status, response.status_code, _WRONG_STATUS_MSG % {
            'method':   'GET',
            'url': url,
            'user': user.username,
            'expected': expected_status,
            'observed': response.status_code
        })
        self.client.logout()

    def _require_authenticated_get_access_not_found(self, url, user):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)

        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.get(url)
        required_result_status = HTTP_404_NOT_FOUND
        self.assertEquals(required_result_status, response.status_code, _WRONG_STATUS_MSG
                          % {
                              'method': 'GET',
                              'url': url,
                              'user': user.username,
                              'expected': required_result_status,
                              'observed': response.status_code})

    def _require_authenticated_get_empty_result(self, url, user):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)

        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.get(url)
        required_result_status = HTTP_200_OK
        self.assertEquals(required_result_status, response.status_code, _WRONG_STATUS_MSG % {
                                'method':   'GET',
                                'url': url,
                                'user': user.username,
                                'expected': required_result_status,
                                'observed': response.status_code})

        self.assertFalse(bool(response.content),
                         'GET %(url)s. Expected an empty list, but got "%(response)s"' % {
            'url': url,
            'response': str(response.content)})

    def _require_authenticated_get_empty_paged_result(self, url, user):
        logged_in = self.client.login(username=user.username,
                                      password=PLAINTEXT_TEMP_USER_PASSWORD)

        self.assertTrue(logged_in, 'Client login failed. Unable to continue with the test.')

        response = self.client.get(url)
        required_result_status = HTTP_200_OK
        self.assertEquals(required_result_status, response.status_code, _WRONG_STATUS_MSG % {
                                'method':   'GET',
                                'url': url,
                                'user': user.username,
                                'expected': required_result_status,
                                'observed': response.status_code})

        content_dict = json.loads(response.content)
        self.assertFalse(bool(content_dict['results']), 'Expected zero result, but got %d' %
                         len(content_dict['results']))
        self.assertEquals(0, content_dict['count'])
        self.assertEquals(None, content_dict['previous'])
        self.assertEquals(None, content_dict['next'])


class StrainResourceTests(MyApiTestCase):
    """
    Tests access controls and HTTP return codes for queries to the /rest/strains REST API resource
    (not any nested resources).

    Strains should only be accessible by:
    1) Superusers
    2) Users who have explicit class-level mutator permissions on Strains via a django.contrib.auth
       permission. Any user with a class-level mutator permission has implied read permission on
       all strains.
    3) Users who have strain read access implied by their read access to an associated study. Since
       EDD only caches the strain name, description, and URL, this should be essentially the same
       visibility granted via access to the study.  There's likely little need for API users to
       access strains in this way, which requires more expensive joins to determine.  However,
       it would be strange to *not* grant read-only access to the strain data already visible
       via the study. Also note that class-level study mutator permissions granted via
       django.contrib.auth do NOT grant strain access, since that permission only gives access to
       the study name/description, not the data or metadata.

    Note that these permissions are enfoced by a combination of EDD's custom
    ModelImplicitViewOrResultImpliedPermissions class and StrainViewSet's get_queryset() method,
    whose non-empty result implies that the requesting user has access to the returned strains.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Creates strains, users, and study/line combinations to test the REST resource's application
        of user permissions.
        """
        super(StrainResourceTests, StrainResourceTests).setUpTestData()

        cls.add_strain_permission = Permission.objects.get(codename='add_strain')
        cls.change_strain_permission = Permission.objects.get(codename='change_strain')
        cls.delete_strain_permission = Permission.objects.get(codename='delete_strain')

        # unprivileged user
        cls.unprivileged_user = User.objects.create_user(username=UNPRIVILEGED_USERNAME,
                                                         email='unprivileged@localhost',
                                                         password=PLAINTEXT_TEMP_USER_PASSWORD)
        # admin user w/ no extra privileges
        cls.superuser = _create_user(username=ADMIN_USERNAME,
                                     email='admin@localhost',
                                     is_superuser=True)

        # plain staff w/ no extra privileges
        cls.staff_user = _create_user(username=STAFF_USERNAME,
                                      email='staff@localhost',
                                      is_staff=True)

        cls.staff_strain_user = _create_user(username='staff.strain.user',
                                             email='staff.study@localhost',
                                             is_staff=True,
                                             manage_perms=(cls.add_strain_permission,
                                                           cls.change_strain_permission,
                                                           cls.delete_strain_permission))

        cls.staff_strain_creator = _create_user(username='staff.strain.creator',
                                                email='staff.study@localhost',
                                                is_staff=True,
                                                manage_perms=(cls.add_strain_permission,))

        cls.staff_strain_changer = _create_user(username='staff.strain.changer',
                                                email='staff.study@localhost',
                                                is_staff=True,
                                                manage_perms=(cls.change_strain_permission,))

        cls.staff_strain_deleter = _create_user(username='staff.strain.deleter',
                                                is_staff=True,
                                                manage_perms=(cls.delete_strain_permission,))

        # set up a study with lines/strains/permissions that allow us to test unprivileged user
        # access to ONLY the strains used in studies the user has read access to.
        cls.study_owner = User.objects.create_user(
            username=STUDY_OWNER_USERNAME,
            email='study_owner@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_read_only_user = User.objects.create_user(
            username=STUDY_READER_USERNAME,
            email='study_read_only@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_write_only_user = User.objects.create_user(
            username=STUDY_WRITER_USERNAME,
            email='study.writer@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_read_group_user = User.objects.create_user(
            username=STUDY_READER_GROUP_USER,
            email='study.group_reader@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_write_group_user = User.objects.create_user(
            username=STUDY_WRITER_GROUP_USER,
            email='study.group_writer@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD
        )

        # create groups for testing group-level user permissions
        study_read_group = Group.objects.create(name='study_read_only_group')
        study_read_group.user_set.add(cls.study_read_group_user)
        study_read_group.save()

        study_write_group = Group.objects.create(name='study_write_only_group')
        study_write_group.user_set.add(cls.study_write_group_user)
        study_write_group.save()

        # create the study
        cls.study = Study.objects.create(name='Test study')

        # future-proof this test by removing any default permissions on the study that may have
        # been configured on this instance (e.g. by the EDD_DEFAULT_STUDY_READ_GROUPS setting).
        # This is most likely to be a complication in development.
        UserPermission.objects.filter(study=cls.study).delete()
        GroupPermission.objects.filter(study=cls.study).delete()

        UserPermission.objects.create(study=cls.study,
                                      user=cls.study_owner,
                                      permission_type=StudyPermission.READ)

        # set permissions on the study
        UserPermission.objects.create(study=cls.study,
                                      user=cls.study_read_only_user,
                                      permission_type=StudyPermission.READ)

        UserPermission.objects.create(study=cls.study,
                                      user=cls.study_write_only_user,
                                      permission_type=StudyPermission.WRITE)

        GroupPermission.objects.create(study=cls.study,
                                       group=study_read_group,
                                       permission_type=StudyPermission.READ)

        GroupPermission.objects.create(study=cls.study,
                                       group=study_write_group,
                                       permission_type=StudyPermission.WRITE)

        # create some strains / lines in the study
        cls.study_strain1 = Strain(name='Study Strain 1',
                                   registry_id=UUID('f120a00f-8bc3-484d-915e-5afe9d890c5f'))
        cls.study_strain1.registry_url = 'https://registry-test.jbei.org/entry/55349'
        cls.study_strain1.save()

        line = Line(name='Study strain1 line', study=cls.study)
        line.save()
        line.strains.add(cls.study_strain1)
        line.save()

    def _enforce_study_strain_read_access(self, url, is_list, strain_in_study=True):
        """
        A helper method that does the work to test permissions for both list and individual strain
        GET access. Note that the way we've constructed test data above,
        :param strain_in_study: True if the provided URL references a strain in our test study,
        False if the strain isn't in the test study, and should only be visible to
        superusers/managers.
        """

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_get_denied(url)

        # verify that various authenticated, but unprivileged users
        # are denied access to strains without class level permission or access to a study that
        # uses them. This is important, because viewing strain names/descriptions for
        # un-publicized studies could compromise the confidentiality of the research before
        # it's published self.require_authenticated_access_denied(self.study_owner)
        require_no_result_method = (self._require_authenticated_get_empty_paged_result if
                                    is_list else
                                    self._require_authenticated_get_empty_result)

        #  enforce access denied behavior for the list resource -- same as just showing an empty
        #  list, since otherwise we'd also return a 403 for a legitimately empty list the user
        #  has access to
        if is_list:
            require_no_result_method(url, self.unprivileged_user)
            require_no_result_method(url, self.staff_user)
            require_no_result_method(url, self.staff_strain_creator)

        # enforce access denied behavior for the strain detail -- permission denied
        else:
            self._require_authenticated_get_denied(url, self.unprivileged_user)
            self._require_authenticated_get_denied(url, self.staff_user)
            self._require_authenticated_get_denied(url, self.staff_strain_creator)

        # test that an 'admin' user can access strains even without the write privilege
        self._require_authenticated_get_allowed(url, self.superuser)

        # test that 'staff' users with any strain mutator privileges have implied read permission
        self._require_authenticated_get_allowed(url, self.staff_strain_changer)
        self._require_authenticated_get_allowed(url, self.staff_strain_deleter)
        self._require_authenticated_get_allowed(url, self.staff_strain_user)

        if strain_in_study:
            # if the strain is in our test study,
            # test that an otherwise unprivileged user with read access to the study can also use
            # the strain resource to view the strain
            self._require_authenticated_get_allowed(url, self.study_owner)
        else:
            # if the strain isn't in our test study, test that the study owner, who has no
            # additional privileges, can't access it
            self._require_authenticated_get_denied(url, self.study_owner)

        # test that user group members with any access to the study have implied read
        # permission on the strains used in it
        if strain_in_study:
            self._require_authenticated_get_allowed(url, self.study_read_group_user)
            self._require_authenticated_get_allowed(url, self.study_write_group_user)
        else:
            self._require_authenticated_get_denied(url, self.study_read_group_user)
            self._require_authenticated_get_denied(url, self.study_write_group_user)

    def test_strain_uuid_pattern_match(self):
        # TODO: test pattern matching for UUID's. had to make code changes during initial testing
        # to enforce matching for UUID's returned by EDD's REST API, which is pretty weird after
        # prior successful tests.
        pass

    def test_strain_delete(self):

        # create a strain to be deleted
        strain = Strain.objects.create(name='To be deleted')

        strain_detail_pattern = '%(base_strain_url)s/%(pk)d/'
        url = strain_detail_pattern % {
            'base_strain_url': STRAINS_RESOURCE_URL,
            'pk': strain.pk,
        }

        # for now, verify that NO ONE can delete a strain via the API. Easier as a stopgap than
        # learning how to ensure that only strains with no foreign keys can be deleted,
        # or implementing / testing a capability to override that check

        # unauthenticated user and unprivileged users get 403
        self.client.logout()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, HTTP_403_FORBIDDEN)
        self._do_delete(url, self.unprivileged_user, HTTP_403_FORBIDDEN)

        # privileged users got 405
        self._do_delete(url, self.staff_strain_deleter, HTTP_405_METHOD_NOT_ALLOWED)
        self._do_delete(url, self.superuser, HTTP_405_METHOD_NOT_ALLOWED)

        # manually delete the strain
        strain.delete()

    def test_strain_add(self):
        """
        Tests that the /rest/strains/ resource responds correctly to configured user permissions
        for adding strains.  Note that django.auth permissions calls this 'add' while DRF
        uses the 'create' action
        """
        print(SEPARATOR)
        print('%s(): ' % self.test_strain_add.__name__)
        print('POST %s' % STRAINS_RESOURCE_URL)
        print(SEPARATOR)

        # Note: missing slash causes 301 response when authenticated
        _URL = STRAINS_RESOURCE_URL + '/'

        # verify that an unprivileged user gets a 403. Note dumps needed for UUID
        post_data = {
            STRAIN_NAME_KEY:        'new strain 1',
            STRAIN_DESCRIPTION_KEY: 'strain 1 description goes here',
            STRAIN_REG_ID_KEY:      '3a3e7b39-258c-4d32-87d6-dd00a66f174f',
            STRAIN_REG_URL_KEY:      'https://registry-test.jbei.org/entry/55350',
        }

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_post_denied(_URL,
                                                  post_data)

        # verify that unprivileged user can't create a strain
        self._require_authenticated_post_denied(_URL,
                                                self.unprivileged_user,
                                                post_data)

        # verify that staff permission alone isn't enough to create a strain
        self._require_authenticated_post_denied(_URL, self.staff_user, post_data)

        # verify that strain change permission doesn't allow addition of new strains
        self._require_authenticated_post_denied(_URL, self.staff_strain_changer, post_data)

        # verify that an administrator can create a strain
        self._require_authenticated_post_allowed(_URL,
                                                 self.superuser,
                                                 post_data)

        # verify that UUID input is ignored during strain creation
        post_data[STRAIN_REG_ID_KEY] = self.study_strain1.registry_id
        response = self._require_authenticated_post_allowed(_URL, self.superuser, post_data)

        self.assertNotEqual(post_data[STRAIN_REG_ID_KEY],
                            json.loads(response.content)[STRAIN_REG_ID_KEY])

        # verify that a user with only explicit create permission can create a strain
        post_data = {
            STRAIN_NAME_KEY:        'new strain 2',
            STRAIN_DESCRIPTION_KEY: 'strain 2 description goes here',
            STRAIN_REG_ID_KEY:       None,
            STRAIN_REG_URL_KEY:      None,
        }
        self._require_authenticated_post_allowed(_URL,
                                                 self.staff_strain_creator,
                                                 post_data)

    def test_strain_change(self):
        print(SEPARATOR)
        print('%s(): ' % self.test_strain_change.__name__)
        print('POST %s' % STRAINS_RESOURCE_URL)
        print(SEPARATOR)

        # Note: missing slash causes 301 response when authenticated
        url_format = '%(resource_url)s/%(id)s/'

        url = url_format % {'resource_url': STRAINS_RESOURCE_URL,
                            'id':           self.study_strain1.pk}

        # define put data for changing every strain field
        put_data = {
            STRAIN_NAME_KEY:        'Holoferax volcanii',
            STRAIN_DESCRIPTION_KEY: 'strain description goes here',
            STRAIN_REG_ID_KEY:      '124bd9ee-7bb5-4266-91e1-6f16682b2b63',
            STRAIN_REG_URL_KEY:     'https://registry-test.jbei.org/entry/64194',
        }

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_put_denied(url, put_data)

        # verify that unprivileged user can't update a strain
        self._require_authenticated_put_denied(url, self.unprivileged_user, put_data)

        # verify that group-level read/write permission on a related study doesn't grant any access
        # to update the contained strains
        self._require_authenticated_put_denied(url, self.study_read_group_user,
                                               put_data)
        self._require_authenticated_put_denied(url,
                                               self.study_write_group_user,
                                               put_data)

        # verify that staff permission alone isn't enough to update a strain
        self._require_authenticated_put_denied(url, self.staff_user, put_data)

        # verify that a user can't update an existing strain with the 'create' permission.
        # See http://www.django-rest-framework.org/api-guide/generic-views/#put-as-create
        self._do_put(url, self.staff_strain_creator, put_data, HTTP_403_FORBIDDEN)

        # verify that the explicit 'change' permission allows access to update the strain
        self._require_authenticated_put_allowed(url, self.staff_strain_changer, put_data)

        # verify that an administrator can update a strain
        self._require_authenticated_put_allowed(url,
                                                self.superuser,
                                                put_data)

    def test_paging(self):
        pass

    def test_strain_list_read_access(self):
        """
            Tests GET /rest/strains
        """
        print(SEPARATOR)
        print('%s(): ' % self.test_strain_list_read_access.__name__)
        print(SEPARATOR)

        list_url = '%s/' % STRAINS_RESOURCE_URL
        print("Testing read access for %s" % list_url)
        self._enforce_study_strain_read_access(list_url, True)

        # create / configure studies and related strains to test strain access via
        # the "everyone" permissions. Note these aren't included in setUpTestData() since that
        # config sets us up for initial tests for results where no strain access is allowed / no
        # results are returned.

        # everyone read
        everyone_read_study = Study.objects.create(name='Readable by everyone')
        EveryonePermission.objects.create(study=everyone_read_study,
                                          permission_type=StudyPermission.READ)
        everyone_read_strain = Strain.objects.create(name='Readable by everyone via study '
                                                          'read')
        line1 = Line.objects.create(name='Everyone read line', study=everyone_read_study)
        line1.strains.add(everyone_read_strain)
        line1.save()

        self._require_authenticated_get_allowed(list_url, self.unprivileged_user,
                                                expected_values=[everyone_read_strain],
                                                values_converter=strain_to_json_dict)

        # everyone write
        everyone_write_study = Study.objects.create(name='Writable be everyone')
        EveryonePermission.objects.create(study=everyone_write_study,
                                          permission_type=StudyPermission.WRITE)
        everyone_write_strain = Strain.objects.create(name='Readable by everyone via study '
                                                           'write')
        line2 = Line.objects.create(name='Everyone write line', study=everyone_write_study)
        line2.strains.add(everyone_write_strain)
        line2.save()

        # test access to strain details via "everyone" read permission
        self._require_authenticated_get_allowed(list_url, self.unprivileged_user,
                                                expected_values=[
                                                           everyone_read_strain,
                                                           everyone_write_strain, ],
                                                values_converter=strain_to_json_dict)

    def test_strain_detail_read_access(self):
        """
            Tests GET /rest/strains
        """
        print(SEPARATOR)
        print('%s(): ' % self.test_strain_detail_read_access.__name__)
        print(SEPARATOR)

        strain_detail_url = '%(base_strain_url)s/%(pk)d/' % {
            'base_strain_url': STRAINS_RESOURCE_URL,
            'pk': self.study_strain1.pk,
        }

        self._enforce_study_strain_read_access(strain_detail_url, False)

        # create a strain so we can test access to its detail view
        strain = Strain.objects.create(name='Test strain',
                                       description='Description goes here')

        # construct the URL for the strain detail view
        strain_detail_pattern = '%(base_strain_url)s/%(pk)d/'
        strain_detail_url = strain_detail_pattern % {
            'base_strain_url': STRAINS_RESOURCE_URL,
            'pk':              strain.pk, }

        # test the strain detail view
        self._enforce_study_strain_read_access(strain_detail_url,
                                               False,
                                               strain_in_study=False)

        # create / configure studies and related strains to test strain access via
        # the "everyone" permissions. Note these aren't included in setUpTestData() since that
        # config sets us up for initial tests for results where no strain access is allowed / no
        # results are returned.

        # everyone read
        everyone_read_study = Study.objects.create(name='Readable by everyone')
        EveryonePermission.objects.create(study=everyone_read_study,
                                          permission_type=StudyPermission.READ)
        everyone_read_strain = Strain.objects.create(name='Readable by everyone via study '
                                                          'read')
        line1 = Line.objects.create(name='Everyone read line', study=everyone_read_study)
        line1.strains.add(everyone_read_strain)
        line1.save()

        everyone_read_url = strain_detail_pattern % {
            'base_strain_url': STRAINS_RESOURCE_URL,
            'pk': everyone_read_strain.pk,
        }

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_get_denied(everyone_read_url)

        self._require_authenticated_get_allowed(everyone_read_url, self.unprivileged_user,
                                                expected_values=everyone_read_strain,
                                                values_converter=strain_to_json_dict)

        # everyone write
        everyone_write_study = Study.objects.create(name='Writable be everyone')
        EveryonePermission.objects.create(study=everyone_write_study,
                                          permission_type=StudyPermission.WRITE)
        everyone_write_strain = Strain.objects.create(name='Readable by everyone via study '
                                                           'write')
        line2 = Line.objects.create(name='Everyone write line', study=everyone_write_study)
        line2.strains.add(everyone_write_strain)
        line2.save()

        everyone_write_url = strain_detail_pattern % {
            'base_strain_url': STRAINS_RESOURCE_URL,
            'pk': everyone_write_strain.pk,
        }

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_get_denied(everyone_read_url)

        # verify study-level "everyone" permissions allow access to view associated strains
        self._require_authenticated_get_allowed(everyone_write_url, self.unprivileged_user,
                                                expected_values=everyone_write_strain,
                                                values_converter=strain_to_json_dict)


def to_paged_result_dict(expected_values, values_converter):
    converted_values = [values_converter(value) for value in expected_values]
    return {
        RESULT_COUNT_KEY: len(converted_values),
        RESULTS_KEY: converted_values,
        PREVIOUS_PAGE_KEY: None,
        NEXT_PAGE_KEY: None,
    }


def compare_paged_result_dict(testcase, expected, observed, order_agnostic=True,
                              partial_response=False):
    """
    A helper method for comparing deserialized JSON result dicts of paged results returned from
    EDD's REST API.
    Provides a  helpful error message if just performing simple exact-match comparison,
    or also supports order agnostic result comparison for cases where a single page of results
    can be reasonably expected to be returned in any order (e.g. when unsorted).
    @param partial_response: True if each provided expected result only contains a partial 
    definition of the object.  In this case, only the provided values will be compared.
    """
    # compare result count
    compare_dict_value(testcase, RESULT_COUNT_KEY, expected, observed)

    # compare next page link
    compare_dict_value(testcase, NEXT_PAGE_KEY, expected, observed)

    # compare prev page link
    compare_dict_value(testcase, PREVIOUS_PAGE_KEY, expected, observed)

    # compare actual result content
    expected = expected[RESULTS_KEY]
    observed = observed[RESULTS_KEY]

    if order_agnostic:
        order_agnostic_result_comparison(testcase, expected, observed, unique_key_name='pk',
                                         partial_response=partial_response)
    else:
        if not partial_response:
            testcase.assertEqual(expected, observed, (
                "Response content didn't match required value(s).\n\n "
                "Expected: %(expected)s\n\n"
                "Observed: %(observed)s" % {
                    'expected': pformat(str(expected)),
                    'observed': pformat(str(observed)),
                }))
        else:
            _compare_partial_value(testcase, expected, observed)


def to_json_comparable_dict(expected_values, values_converter):
    """
    Converts expected value(s) for a REST API request into a dictionary that's easily
    comparable against deserialized JSON results actually returned by the API during the test.
    :param expected_values: a single expected value or an iterable of expected values to
    structure in the arrangement as a deserialized JSON string received from the REST API.
    :param values_converter: a function to use for converting expected values specified in the
    test into the expected dictionary form to match deserialized JSON
    :return: a dict of expected values that should match the REST JSON response
    """
    if isinstance(expected_values, collections.Iterable):
        return to_paged_result_dict(expected_values, values_converter)
    else:
        return values_converter(expected_values)


err_msg = 'Expected %(key)s "%(expected)s", but observed "%(observed)s"'


def compare_dict_value(testcase, key, expected_values, observed_values):
    """
        A helper method to provide a more clear error message when a test assertion fails
    """
    expected = expected_values[key]
    observed = observed_values[key]
    testcase.assertEqual(expected, observed, err_msg % {
        'key': key,
        'expected': str(expected),
        'observed': str(observed),
    })


def order_agnostic_result_comparison(testcase, expected_values_list, observed_values_list,
                                     unique_key_name='pk', partial_response=False):
    """
    A helper method for comparing query results in cases where top-lever result order doesn't 
    matter, only content. For example, if user didn't specify any sort parameter in the query, 
    order of results is unpredictable.

    Note that this method is only appropriate to use when there's only a single page of results,
    otherwise there's no guarantee of which results appear in the first page.
    @param partial_response: True if the expected value objects only contain a subset of the 
    response (e.g. they may be missing pk's, UUID's or other data that were autogenerated by 
    EDD). If True, only the expected values defined in the input will be compared, and any other
    results will be ignored.
    """

    # build dicts mapping unique id -> content for each result. requires more memory,
    # but a lot less code to compare this way.
    expected_values_dict = {value[unique_key_name]: value for value in expected_values_list}
    observed_values_dict = {value[unique_key_name]: value for value in observed_values_list}

    unique_keys = set(expected_values_dict.keys())
    unique_keys.update(observed_values_dict.keys())

    not_defined_val = '[Not defined]'
    header = '%(unique key)s\tExpected\tObserved'
    results_summary = '\n'.join(['%(key)s:\t%(expected)s\t%(observed)s' % {
        'key': str(key),
        'expected': str(expected_values_dict.get(key, not_defined_val)),
        'observed': str(observed_values_dict.get(key, not_defined_val))

    } for key in unique_keys])

    if not partial_response:
        testcase.assertEqual(expected_values_dict, observed_values_dict,
                             "Query results didn't match expected values.\n"
                             "%(header)s\n\n%(results_summary)s" % {
                                 'header': header,
                                 'results_summary': results_summary,
                             })
    else:
        _compare_partial_value(testcase, expected_values_dict, observed_values_dict)


def _compare_partial_value(testcase, exp_value, observed_value):
    """
    A helper method for comparing nested results.  Dictionaries are compared without order taken
    into consideration, while all other elements are 
    :param testcase: 
    :param exp_value: 
    :param observed_value: 
    :return: 
    """

    if isinstance(exp_value, dict):
        for unique_key, exp_inner in exp_value.iteritems():
            obs_inner = observed_value[unique_key]
            _compare_partial_value(testcase, exp_inner, obs_inner)

    elif isinstance(exp_value, collections.Sequence) and not isinstance(exp_value, basestring):
        for index, exp_inner in enumerate(exp_value):
            obs_inner = observed_value[index]
            print('Expected value %s' % str(exp_inner))  # TODO: remove debug stmt
            _compare_partial_value(testcase, exp_inner, obs_inner)
    else:
        testcase.assertEqual(exp_value, observed_value,
                             'Expected value %(exp)s but observed %(obs)s' % {
                                 'exp': exp_value,
                                 'obs': observed_value, })


def strain_to_json_dict(strain):
    if not strain:
        return {}

    return {
        'name':         strain.name,
        'description': strain.description,
        'registry_url': strain.registry_url,
        'registry_id': strain.registry_id,
        'pk': strain.pk
    }


def study_to_json_dict(study):
    if not study:
        return {}

    val = {
        'slug': study.slug,
        'pk': study.pk,
        'active': study.active,
    }
    edd_obj_to_json_dict(study, val)
    return val


def edd_obj_to_json_dict(edd_obj, dict):
    if not edd_obj:
        return

    dict['name'] = edd_obj.name
    dict['description'] = edd_obj.description
    dict['uuid'] = unicode(edd_obj.uuid)
    dict['active'] = edd_obj.active


def _create_user(username, email='staff.study@localhost',
                 is_superuser=False,
                 is_staff=True, manage_perms=()):
    """
        A convenience method that creates and returns a test User, with requested
        permissions set. Helps avoid verification problems when database state has been correctly
        configured, but locally cached user objects aren't up-to-date with the database.
    """

    # create and save the user so foreign key based permissions changes will succeed.
    # note: some password is required to allow successful login
    user = User.objects.create_user(username=username,
                                    email=email,
                                    password=PLAINTEXT_TEMP_USER_PASSWORD)

    # return early if no updates to user or its foreign key relationships
    if not (is_staff or is_superuser):
        return

    user.is_staff = is_staff
    user.is_superuser = is_superuser

    if is_staff:
        for permission in manage_perms:
            user.user_permissions.add(permission)

    user.save()

    # re-fetch user from database to force permissions
    # refresh http://stackoverflow.com/questions/10102918/cant-change-user-permissions-during
    # -unittest-in-django
    user = User.objects.get(username=username)

    return user


class StudyResourceTests(MyApiTestCase):
    """
    Tests access controls and HTTP return codes for queries to the base /rest/studies REST API
    resource (not any nested resources).

    Studies should only be accessible by:
    1) Superusers
    2) Users who have explicit class-level mutator permissions on Studies via a django.contrib.auth
       permission. Any user with a class-level mutator permission has implied read permission on
       the basic study name/description, though not necessarily on the contained lines/assays
       or data.
    3) Users who have explicit StudyPermission granted via their individual account or via user
    group membership.

    Note that these permissions are enfoced by a combination of EDD's custom
    ModelImplicitViewOrResultImpliedPermissions class and StudyViewSet's get_queryset() method,
    whose non-empty result implies that the requesting user has access to the returned strains.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Creates strains, users, and study/line combinations to test the REST resource's application
        of user permissions.
        """
        super(StudyResourceTests, StudyResourceTests).setUpTestData()

        cls.add_study_permission = Permission.objects.get(codename='add_study')
        cls.change_study_permission = Permission.objects.get(codename='change_study')
        cls.delete_study_permission = Permission.objects.get(codename='delete_study')

        # unprivileged user
        cls.unprivileged_user = User.objects.create_user(username=UNPRIVILEGED_USERNAME,
                                                         email='unprivileged@localhost',
                                                         password=PLAINTEXT_TEMP_USER_PASSWORD)
        # admin user w/ no extra privileges
        cls.superuser = _create_user(username=ADMIN_USERNAME,
                                     email='admin@localhost',
                                     is_superuser=True)

        # plain staff w/ no extra privileges
        cls.staff_user = _create_user(username=STAFF_USERNAME,
                                      email='staff@localhost',
                                      is_staff=True)

        cls.staff_study_creator = _create_user(username='staff.study.creator',
                                               email='staff.study@localhost',
                                               is_staff=True,
                                               manage_perms=(cls.add_study_permission,))

        cls.staff_study_changer = _create_user(username='staff.study.changer',
                                               email='staff.study@localhost',
                                               is_staff=True,
                                               manage_perms=(cls.change_study_permission,))

        cls.staff_study_deleter = _create_user(username='staff.study.deleter',
                                               is_staff=True,
                                               manage_perms=(cls.delete_study_permission,))

        cls.study_read_only_user = User.objects.create_user(
            username=STUDY_READER_USERNAME,
            email='study_read_only@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_write_only_user = User.objects.create_user(
            username=STUDY_WRITER_USERNAME,
            email='study.writer@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_read_group_user = User.objects.create_user(
            username=STUDY_READER_GROUP_USER,
            email='study.group_reader@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD)

        cls.study_write_group_user = User.objects.create_user(
            username=STUDY_WRITER_GROUP_USER,
            email='study.group_writer@localhost',
            password=PLAINTEXT_TEMP_USER_PASSWORD
        )

        cls.study_default_read_group_user = User.objects.create_user(
                username='Default read group user',
                email='study.default_read_group.user',
                password=PLAINTEXT_TEMP_USER_PASSWORD,
        )

        # create groups for testing group-level user permissions
        study_read_group = Group.objects.create(name='study_read_only_group')
        study_read_group.user_set.add(cls.study_read_group_user)
        study_read_group.save()

        study_write_group = Group.objects.create(name='study_write_only_group')
        study_write_group.user_set.add(cls.study_write_group_user)
        study_write_group.save()

        cls.study_default_read_group = Group.objects.create(name='study_default_read_group')
        cls.study_default_read_group.user_set.add(cls.study_default_read_group_user)
        cls.study_default_read_group.save()

        # create the study
        cls.study = Study.objects.create(name='Test study')

        # future-proof this test by removing any default permissions on the study that may have
        # been configured on this instance (e.g. by the EDD_DEFAULT_STUDY_READ_GROUPS setting).
        # This is most likely to be a complication in development.
        UserPermission.objects.filter(study=cls.study).delete()
        GroupPermission.objects.filter(study=cls.study).delete()

        # set permissions on the study
        UserPermission.objects.create(study=cls.study,
                                      user=cls.study_read_only_user,
                                      permission_type=StudyPermission.READ)

        UserPermission.objects.create(study=cls.study,
                                      user=cls.study_write_only_user,
                                      permission_type=StudyPermission.WRITE)

        GroupPermission.objects.create(study=cls.study,
                                       group=study_read_group,
                                       permission_type=StudyPermission.READ)

        GroupPermission.objects.create(study=cls.study,
                                       group=study_write_group,
                                       permission_type=StudyPermission.WRITE)

    def _enforce_study_read_access(self, url, is_list, expected_values):
        """
        A helper method that does the work to test permissions for both list and individual study
        GET access.
        """

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_get_denied(url)

        # verify that various authenticated, but unprivileged users
        # are denied access to studies without class level permission or access to a study that
        # uses them. This is important, because viewing strain names/descriptions for
        # un-publicized studies could compromise the confidentiality of the research before
        # it's published self.require_authenticated_access_denied(self.study_owner)
        require_no_result_method = (self._require_authenticated_get_empty_paged_result if
                                    is_list else self._require_authenticated_get_empty_result)

        #  enforce access denied behavior for the list resource -- same as just showing an empty
        #  list, since otherwise we'd also return a 403 for a legitimately empty list the user
        #  has access to
        if is_list:
            require_no_result_method(url, self.unprivileged_user)
            require_no_result_method(url, self.staff_user)
            require_no_result_method(url, self.staff_study_creator)

        # enforce access denied behavior for the study detail -- permission denied
        else:
            self._require_authenticated_get_denied(url, self.unprivileged_user)
            self._require_authenticated_get_denied(url, self.staff_user)
            self._require_authenticated_get_denied(url, self.staff_study_creator)

        # test that users / groups with read access can read the study
        self._require_authenticated_get_allowed(url, self.study_read_only_user,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

        self._require_authenticated_get_allowed(url, self.study_read_group_user,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

        # verify that study write permissions imply read permissions
        self._require_authenticated_get_allowed(url, self.study_write_only_user,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

        self._require_authenticated_get_allowed(url, self.study_write_group_user,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

        # test that an 'admin' user can access study data without other privileges
        self._require_authenticated_get_allowed(url, self.superuser,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

        # test that 'staff' users with any study mutator privileges have implied read permission
        self._require_authenticated_get_allowed(url, self.staff_study_changer,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)
        self._require_authenticated_get_allowed(url, self.staff_study_deleter,
                                                expected_values=expected_values,
                                                values_converter=study_to_json_dict,
                                                partial_response=True)



    # def test_study_delete(self):
    #     """
    #         Enforces that study deletion is not allowed via the API
    #     """
    #
    #     # create a study to be deleted
    #     study = Study.objects.create(name='To be deleted')
    #
    #     study_detail_pattern = '%(base_study_url)s/%(pk)d/'
    #     url = study_detail_pattern % {
    #         'base_study_url': STUDIES_RESOURCE_URL,
    #         'pk': study.pk,
    #     }
    #
    #     # unauthenticated user and unprivileged users get 403
    #     self.client.logout()
    #     response = self.client.delete(url)
    #     self.assertEqual(response.status_code, HTTP_403_FORBIDDEN)
    #     self._do_delete(url, self.unprivileged_user, HTTP_403_FORBIDDEN)
    #
    #     # privileged users got 405
    #     self._do_delete(url, self.staff_study_deleter, HTTP_405_METHOD_NOT_ALLOWED)
    #     self._do_delete(url, self.superuser, HTTP_405_METHOD_NOT_ALLOWED)
    #
    #     # delete the study via the ORM
    #     study.delete()

    def test_study_add(self):
        """
        Tests that the /rest/strains/ resource responds correctly to configured user permissions
        for adding strains.  Note that django.auth permissions calls this 'add' while DRF
        uses the 'create' action
        """
        # Note: missing slash causes 301 response when authenticated
        _URL = STUDIES_RESOURCE_URL + '/'

        print(SEPARATOR)
        print('%s(): ' % self.test_study_add.__name__)
        print('POST %s' % _URL)
        print(SEPARATOR)

        # Note on use of settings in this method: instead of using SimpleTestCase.settings()
        # context manager as recommended, we have to manually set value for our custom EDD
        # settings.  The context manager only appears to work for built-in Django settings,
        # or at least doesn't seem to work in the context of DRF's APITestCase.

        # verify that an unprivileged user gets a 403. Note dumps needed for UUID
        post_data = {
            STUDY_NAME_KEY:        'new study 1',
            STUDY_DESCRIPTION_KEY: 'strain 1 description goes here',
        }

        # verify that an un-authenticated request gets a 404
        self._require_unauthenticated_post_denied(_URL, post_data)

        _SUPERUSER_CREATE_TEMP = (settings.EDD_ONLY_SUPERUSER_CREATE
                                  if hasattr(settings, 'EDD_ONLY_SUPERUSER_CREATE') else None)

        _DEFAULT_GRPS_TEMP = (settings.EDD_DEFAULT_STUDY_READ_GROUPS
                              if hasattr(settings, 'EDD_DEFAULT_STUDY_READ_GROUPS')
                              else None)

        try:
            # with normal settings, verify all users can create studies, regardless of privileges
            settings.EDD_ONLY_SUPERUSER_CREATE = False
            self._require_authenticated_post_allowed(_URL,
                                                     self.unprivileged_user,
                                                     post_data,
                                                     required_response=post_data,
                                                     partial_response=True)

            #######################################################################################
            settings.EDD_ONLY_SUPERUSER_CREATE = True
            #######################################################################################

            if hasattr(settings, 'EDD_ONLY_SUPERUSER_CREATE'):
                print('EDD_ONLY_SUPERUSER_CREATE  : %s' % settings.EDD_ONLY_SUPERUSER_CREATE)
            else:
                print('EDD_ONLY_SUPERUSER_CREATE setting is undefined')
            self._require_authenticated_post_denied(_URL, self.unprivileged_user, post_data)

            self._require_authenticated_post_denied(_URL, self.staff_user, post_data)

            # verify that study change permission doesn't allow addition of new studies
            self._require_authenticated_post_denied(_URL, self.staff_study_changer,
                                                    post_data)

            # verify that an administrator can create a study
            self._require_authenticated_post_allowed(_URL, self.superuser, post_data)

            # verify that even a user with the study create privilege can't create a study
            self._require_authenticated_post_denied(_URL, self.staff_study_creator,
                                                    post_data)

            #######################################################################################
            settings.EDD_ONLY_SUPERUSER_CREATE = 'permission'
            #######################################################################################
            # verify that when the setting is set appropriately, the study create privilege is
            # sufficient to allow a privileged user to create a study
            self._require_authenticated_post_allowed(_URL,
                                                     self.staff_study_creator,
                                                     post_data)

            self._require_authenticated_post_denied(_URL, self.unprivileged_user, post_data)

            self._require_authenticated_post_denied(_URL, self.staff_user, post_data)

            # verify that study change permission doesn't allow addition of new studies
            self._require_authenticated_post_denied(_URL, self.staff_study_changer,
                                                    post_data)

            # verify that an administrator can create a study
            self._require_authenticated_post_allowed(_URL, self.superuser, post_data)

            #######################################################################################
            #######################################################################################

            # verify that UUID input is ignored during study creation
            post_data[UUID_KEY] = str(self.study.uuid)
            # TODO: remove print stmt
            print('Attempting to create a study with duplicate UUID %s' % str(self.study.uuid))
            response = self._require_authenticated_post_allowed(_URL, self.superuser, post_data)
            self.assertNotEqual(post_data[UUID_KEY], json.loads(response.content)[UUID_KEY])

        # restore previous settings values altered during the test
        finally:

            if _SUPERUSER_CREATE_TEMP is None:
                del settings.EDD_ONLY_SUPERUSER_CREATE
            else:
                settings.EDD_ONLY_SUPERUSER_CREATE = _SUPERUSER_CREATE_TEMP

            if _DEFAULT_GRPS_TEMP is None:
                del settings.EDD_DEFAULT_STUDY_READ_GROUPS
            else:
                settings.EDD_DEFAULT_STUDY_READ_GROUPS = _DEFAULT_GRPS_TEMP


    # def test_study_change(self):
    #     print(SEPARATOR)
    #     print('%s(): ' % self.test_study_change.__name__)
    #     print('POST %s' % STUDIES_RESOURCE_URL)
    #     print(SEPARATOR)
    #
    #     # Note: missing slash causes 301 response when authenticated
    #     url_format = '%(resource_url)s/%(id)s/'
    #
    #     url = url_format % {'resource_url': STUDIES_RESOURCE_URL,
    #                         'id':           self.study.pk}
    #
    #     # define put data for changing every strain field
    #     put_data = {
    #         STUDY_NAME_KEY:        'Test study',
    #         STUDY_DESCRIPTION_KEY: 'Description goes here',
    #     }
    #
    #     # verify that an un-authenticated request gets a 404
    #     self._require_unauthenticated_put_access_denied(url,
    #                                                     put_data)
    #
    #     # verify that unprivileged user can't update someone else's study
    #     self._require_authenticated_put_access_denied(url,
    #                                                   self.unprivileged_user,
    #                                                   put_data)
    #
    #     self._require_authenticated_put_access_denied(url, self.study_read_group_user,
    #                                                   put_data)
    #
    #     self._require_authenticated_put_access_allowed(url,
    #                                                    self.study_write_group_user,
    #                                                    put_data)
    #
    #     # verify that staff permission alone isn't enough to update a study
    #     self._require_authenticated_put_access_denied(url, self.staff_user, put_data)
    #
    #     # verify that a user can't update an existing study with the 'create' permission.
    #     # See http://www.django-rest-framework.org/api-guide/generic-views/#put-as-create
    #     self._do_put(url, self.staff_study_creator, put_data, HTTP_403_FORBIDDEN)
    #
    #     # verify that the explicit 'change' permission allows access to update the strain
    #     self._require_authenticated_put_access_allowed(url, self.staff_study_changer, put_data)
    #
    #     # verify that an administrator can update a strain
    #     self._require_authenticated_put_access_allowed(url,
    #                                                    self.superuser,
    #                                                    put_data)


    def test_study_list_read_access(self):
        """
            Tests GET /rest/studies/
        """
        print(SEPARATOR)
        print('%s(): ' % self.test_study_list_read_access.__name__)
        print(SEPARATOR)

        list_url = '%s/' % STUDIES_RESOURCE_URL
        print("Testing read access for %s" % list_url)
        self._enforce_study_read_access(list_url, True, expected_values=[self.study])

        # create / configure studies and related strains to test strain access via
        # the "everyone" permissions. Note these aren't included in setUpTestData() since that
        # config sets us up for initial tests for results where no strain access is allowed / no
        # results are returned.

        # everyone read
        everyone_read_study = Study.objects.create(name='Readable by everyone')
        EveryonePermission.objects.create(study=everyone_read_study,
                                          permission_type=StudyPermission.READ)

        self._require_authenticated_get_allowed(list_url, self.unprivileged_user,
                                                expected_values=[everyone_read_study],
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

        # everyone write
        everyone_write_study = Study.objects.create(name='Writable be everyone')
        EveryonePermission.objects.create(study=everyone_write_study,
                                          permission_type=StudyPermission.WRITE)

        self._require_authenticated_get_allowed(list_url, self.unprivileged_user,
                                                expected_values=[
                                                           everyone_read_study,
                                                           everyone_write_study, ],
                                                values_converter=study_to_json_dict,
                                                partial_response=True)

    def test_study_detail_read_access(self):
        """
            Tests GET /rest/studies
        """
        print(SEPARATOR)
        print('%s(): ' % self.test_study_detail_read_access.__name__)
        print(SEPARATOR)

        # build up a list of all the valid URL's by which the study details can be accessed\
        study_detail_urls = make_study_url_variants(self.study)

        # test that permissions are applied consistently across each URL used to access the study
        for study_detail_url in study_detail_urls:
            self._enforce_study_read_access(study_detail_url, False, expected_values=self.study)

        # create / configure studies and related strains to test strain access via
        # the "everyone" permissions. Note these aren't included in setUpTestData() since that
        # config sets us up for initial tests for results where no strain access is allowed / no
        # results are returned.

        # everyone read
        everyone_read_study = Study.objects.create(name='Readable by everyone')
        EveryonePermission.objects.create(study=everyone_read_study,
                                          permission_type=StudyPermission.READ)

        everyone_read_urls = make_study_url_variants(everyone_read_study)
        for everyone_read_url in everyone_read_urls:

            # verify that an un-authenticated request gets a 404
            self._require_unauthenticated_get_denied(everyone_read_url)

            self._require_authenticated_get_allowed(everyone_read_url, self.unprivileged_user,
                                                    expected_values=everyone_read_study,
                                                    values_converter=study_to_json_dict,
                                                    partial_response=True)

        # everyone write
        everyone_write_study = Study.objects.create(name='Writable be everyone')
        EveryonePermission.objects.create(study=everyone_write_study,
                                          permission_type=StudyPermission.WRITE)

        everyone_write_urls = make_study_url_variants(everyone_write_study)
        for everyone_write_url in everyone_write_urls:

            # verify that an un-authenticated request gets a 404
            self._require_unauthenticated_get_denied(everyone_write_url)

            # verify study-level "everyone" permissions allow access to view associated strains
            self._require_authenticated_get_allowed(everyone_write_url, self.unprivileged_user,
                                                    expected_values=everyone_write_study,
                                                    values_converter=study_to_json_dict,
                                                    partial_response=True)


def make_study_url_variants(study):
    study_detail_pattern = '%(base_studies_url)s/%(id)s/'
    pk_based_url = study_detail_pattern % {
        'base_studies_url': STUDIES_RESOURCE_URL, 'id': str(study.pk),
    }
    uuid_based_url = study_detail_pattern % {
        'base_studies_url': STUDIES_RESOURCE_URL, 'id': str(study.uuid),
    }
    slug_based_url = study_detail_pattern % {
        'base_studies_url': STUDIES_RESOURCE_URL, 'id': str(study.slug),
    }
    return (pk_based_url, uuid_based_url, slug_based_url, )


def make_url_variants(list_url, edd_obj):
    pattern = list_url + '/%s/'

    return (pattern % edd_obj.pk, pattern % str(edd_obj.uuid), )