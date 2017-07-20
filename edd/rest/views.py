"""
Defines the supported views and browsable API endpoint documentation for EDD's REST framework.
This class is a work in progress.

Assuming Django REST Framework (DRF) will be adopted in EDD, new and existing views should be
ported to this class over time. Many REST resources are currently defined in main/views.py,
but are not making use of DRF.

Note that many of the docstrings in this module use specific YAML formatting to define API
endpoint documentation viewable in the browser. See
http://django-rest-swagger.readthedocs.io/en/latest/yaml.html
"""
from __future__ import unicode_literals

import json
import logging
import numbers
import re
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, response, schemas, status, viewsets
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.exceptions import APIException, ParseError, ValidationError, NotAuthenticated, NotFound
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.relations import StringRelatedField
from rest_framework.response import Response
from rest_framework.status import HTTP_403_FORBIDDEN
from rest_framework.viewsets import GenericViewSet
from rest_framework_swagger.renderers import OpenAPIRenderer, SwaggerUIRenderer

from .permissions import (ImpliedPermissions, StudyResourcePermissions,
                          user_has_admin_or_manage_perm)
from .serializers import (LineSerializer, MeasurementUnitSerializer,
                          MetadataGroupSerializer, MetadataTypeSerializer,
                          ProtocolSerializer, StrainSerializer, StudySerializer,
                          UserSerializer, AssaySerializer)
from jbei.rest.clients.edd.constants import (CASE_SENSITIVE_PARAM, CREATED_AFTER_PARAM,
                                             CREATED_BEFORE_PARAM, ACTIVE_STATUS_DEFAULT,
                                             ACTIVE_STATUS_PARAM, METADATA_TYPE_CONTEXT,
                                             METADATA_TYPE_GROUP, METADATA_TYPE_I18N,
                                             METADATA_TYPE_LOCALE, METADATA_TYPE_NAME_REGEX,
                                             QUERY_ACTIVE_OBJECTS_ONLY, QUERY_ANY_ACTIVE_STATUS,
                                             QUERY_INACTIVE_OBJECTS_ONLY, STRAIN_CASE_SENSITIVE,
                                             STRAIN_NAME, STRAIN_NAME_REGEX, STRAIN_REGISTRY_ID,
                                             STRAIN_REGISTRY_URL_REGEX, STUDIES_RESOURCE_NAME, LINES_RESOURCE_NAME,
                                             STUDY_LINE_NAME_REGEX, UPDATED_AFTER_PARAM,
                                             UPDATED_BEFORE_PARAM, ACTIVE_STATUS_PARAM,
                                             NAME_REGEX_PARAM, DESCRIPTION_REGEX_PARAM,
                                             META_KEY_PARAM, META_OPERATOR_PARAM, META_VALUE_PARAM,
                                             META_SEARCH_PARAM, SEARCH_TYPE_LINES,
                                             SEARCH_TYPE_STUDIES, SEARCH_TYPE_MEASUREMENT_UNITS,
                                             SEARCH_TYPE_METADATA_TYPES, SEARCH_TYPE_PROTOCOLS,
                                             SEARCH_TYPE_STRAINS, SEARCH_TYPE_METADATA_GROUPS,
                                             UNIT_NAME_PARAM, ALT_NAMES_PARAM, TYPE_GROUP_PARAM,
                                             SEARCH_TYPE_PARAM)
from jbei.rest.utils import is_numeric_pk
from main.models import (Assay, Line, MeasurementUnit, MetadataGroup, MetadataType, Protocol, Strain,
                         Study, StudyPermission, User)

logger = logging.getLogger(__name__)

# Note on REST resource permissions:
# Many important resources below require some cludgy code to work with DjangoModelPermissions (a
# placeholder QuerySet in addition to overriding get_queryset()). See
# http://www.django-rest-framework.org/api-guide/permissions/#djangomodelpermissions

# class IsStudyReadable(permissions.BasePermission):
#     """
#     Custom permission to only allow owners of an object to edit it.
#     """
#
#     def has_object_permission(self, request, view, study):
#
#         # studies are only available to users who have read permissions on them
#         return study.user_can_read(request.user)

STRAIN_NESTED_RESOURCE_PARENT_PREFIX = r'strains'

STUDY_URL_KWARG = 'study'
BASE_STRAIN_URL_KWARG = 'id'  # NOTE: value impacts url kwarg names for nested resources
HTTP_MUTATOR_METHODS = ('POST', 'PUT', 'PATCH', 'UPDATE', 'DELETE')
EXISTING_RECORD_MUTATOR_METHODS = ('PUT', 'PATCH', 'UPDATE', 'DELETE')

SORT_PARAM = 'sort_order'
FORWARD_SORT_VALUE = 'ascending'
REVERSE_SORT_VALUE = 'descending'

USE_STANDARD_PERMISSIONS = None

# Subset of Django 1.11-supported HStoreField operators that don't require a key name in
# order to use them. Note: 'contains'/'contained_by' work both with and without a key
NON_KEY_DJANGO_HSTORE_COMPARISONS = ('has_key', 'has_any_keys', 'has_keys', 'keys', 'values')


def permission_denied_handler(request):
    # same as DRF provides in /rest/
    return HttpResponse('{"detail":"Authentication credentials were not provided."}',
                        HTTP_403_FORBIDDEN)


@api_view()
@renderer_classes([OpenAPIRenderer, SwaggerUIRenderer])
def schema_view(request):
    generator = schemas.SchemaGenerator(title='Experiment Data Depot')
    return response.Response(generator.get_schema(request=request))


class AssaysViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ImpliedPermissions]
    serializer_class = AssaySerializer
    lookup_url_kwarg = 'assay_id'
    STUDY_URL_KWARG = '%s_pk' % STUDIES_RESOURCE_NAME
    LINE_URL_KWARG = 'line_line_pk'  # TODO: sort out weird router/View.lookup_url_kwarg naming for double-nesting

    def get_object(self):
        """
        Overrides the default implementation to provide flexible lookup for Assay detail
        views (either based on local numeric primary key, or UUID)
        """
        queryset = self.get_queryset()

        # unlike the DRF example code: for consistency in permissions enforcement, just do all the
        # filtering in get_queryset() and pass empty filters here
        filters = {}
        obj = get_object_or_404(queryset, **filters)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):

        logger.debug('in %(class)s.%(method)s' % {
            'class': AssaysViewSet.__name__,
            'method': self.get_queryset.__name__
        })

        query_params = self.request.query_params

        user = self.request.user
        if not user.is_authenticated():
            logger.debug('User %s is not authenticated' % user.username)
            raise NotAuthenticated()

        # load / check study permissions first rather than using expensive joins that include
        # Study/StudyPermission/Line/Assay
        study_id = self.kwargs[self.STUDY_URL_KWARG]
        study_query_params = {ACTIVE_STATUS_PARAM: QUERY_ANY_ACTIVE_STATUS}  # ignore active status for enclosing study
        study_query = build_study_query(self.request, study_query_params, identifier=study_id, skip_study_manage_perms=True)
        study_query = study_query.values_list('pk', flat=True)
        if len(study_query) != 1:
            logger.debug('Study %(study)s not found, or user %(user)s does not have permission' % {
                'study': study_id,
                'user': user.username})
            raise NotFound('Study %s not found' % study_id)

        # load the line next to be sure it actually exists in this study. otherwise we're either performing a more
        # expensive assay/line join or trusting users to provide a valid assay ID within the study (exposing all study
        # assays instead of only those the user has access to)
        line_id = self.kwargs[self.LINE_URL_KWARG]
        study_pk = study_query.get()
        line_query = do_id_filter(Line.objects.filter(study__pk=study_pk), line_id)

        if not line_query:
            msg = 'Line "%(line)s" not found in study "%(study)s"' % {
                'line': line_id,
                'study': study_id,
            }
            logger.info(msg)
            raise NotFound(msg)

        assays_query = Assay.objects.filter(line__pk=line_query.get().pk)

        assay_id = self.kwargs.get(self.lookup_url_kwarg)
        return optional_edd_object_filtering(query_params,
                                                     assays_query,
                                                     identifier_override=assay_id)

    def get_serializer_class(self):
        # TODO: override to support optional bulk measurement / data requests for the study rather than returning just
        # assays
        return super(AssaysViewSet, self).get_serializer_class()


class MetadataTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that supports viewing and searching .EDD's metadata types
    TODO: implement/confirm access controls for unsafe methods, then make writable
    """

    # Note: queryset must be defined for DjangoModelPermissions in addition to get_queryset(). See
    # related  comment/URL above
    permission_classes = [ImpliedPermissions]
    serializer_class = MetadataTypeSerializer

    def get_queryset(self):
        identifier = self.kwargs.get('pk', None)

        queryset = MetadataType.objects.all()
        return build_metadata_type_query(queryset, self.request.query_params,
                                         identifier=identifier)


def do_id_filter(queryset, identifier):
    try:
        queryset = queryset.filter(pk=int(identifier))
    except ValueError:
        try:
            queryset = queryset.filter(uuid=UUID(identifier))
        except ValueError:
            raise ParseError('Invalid identifier "%(id)s"' % {
                'id': identifier
            })

    return queryset


def build_metadata_type_query(queryset, query_params, identifier=None):
    if identifier:
        try:
            queryset = queryset.filter(pk=identifier)
        except ValueError:
            try:
                queryset = queryset.filter(uuid=UUID(identifier))
            except ValueError:
                raise ValidationError('Invalid identifier "%(id)s"' % {
                    'id': identifier
                })

    if not query_params:
        return queryset

    # group id
    group_id = query_params.get(METADATA_TYPE_GROUP)
    if group_id:
        if is_numeric_pk(group_id):
            queryset = queryset.filter(group=group_id)
        else:
            queryset = queryset.filter(group__group_name=group_id)

    # for context
    for_context = query_params.get(METADATA_TYPE_CONTEXT)
    if for_context:
        queryset = queryset.filter(for_context=for_context)

    # type I18N
    type_i18n = query_params.get(METADATA_TYPE_I18N)
    if type_i18n:
        queryset = queryset.filter(type_i18n=type_i18n)

    # sort
    sort = query_params.get(SORT_PARAM)

    TYPE_NAME_PROPERTY = 'type_name'

    if sort is not None:
        queryset = queryset.order_by(TYPE_NAME_PROPERTY)

        if sort == REVERSE_SORT_VALUE:
            queryset = queryset.reverse()

    queryset = _optional_regex_filter(query_params, queryset, TYPE_NAME_PROPERTY,
                                      METADATA_TYPE_NAME_REGEX, METADATA_TYPE_LOCALE, )

    return queryset


OWNED_BY = 'owned_by'
VARIANT_OF = 'variant_of'
DEFAULT_UNITS_QUERY_PARAM = 'default_units'
CATEGORIZATION_QUERY_PARAM = 'categorization'


# TODO: make writable for users with permission
class MeasurementUnitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MeasurementUnit.objects.all()  # must be defined for DjangoModelPermissions
    serializer_class = MeasurementUnitSerializer

    def get_queryset(self):

        queryset = MeasurementUnit.objects.all()

        # Note: at the time of writing, MeasurementUnit doesn't support a UUID
        pk = self.kwargs.get('pk', None)

        return build_measurement_units_query(self.request.query_params, queryset, pk)


def build_measurement_units_query(query_params, queryset, identifier=None):
    # Note: at the time of writing, MeasurementUnit doesn't support a UUID
    if identifier:
        queryset = queryset.filter(pk=identifier)

    i18n_placeholder = ''

    queryset = _optional_regex_filter(query_params, queryset, 'unit_name', UNIT_NAME_PARAM,
                                      i18n_placeholder)

    queryset = _optional_regex_filter(query_params, queryset, 'alternate_names',
                                      ALT_NAMES_PARAM, i18n_placeholder)

    queryset = _optional_regex_filter(query_params, queryset, 'type_group', TYPE_GROUP_PARAM,
                                      i18n_placeholder)

    return queryset


class ProtocolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Protocol.objects.all()  # must be defined for DjangoModelPermissions
    serializer_class = ProtocolSerializer

    # Django model object property (used several times)
    NAME_PROPERTY = 'name'

    # API query parameter names...may diverge from Django Model field names over time
    NAME_QUERY_PARAM = 'name'
    OWNED_BY_QUERY_PARAM = 'owned_by'
    CATEGORIZATION_PROPERTY = 'categorization'
    DEFAULT_UNITS_PROPERTY = 'default_units'

    def get_queryset(self):
        pk = self.kwargs.get('pk', None)

        queryset = Protocol.objects.all()
        if pk:
            if is_numeric_pk(pk):
                queryset = queryset.filter(pk=pk)
            # TODO: revisit / retest UUID-based lookup...not working
            else:
                queryset = queryset.filter(uuid=pk)

        i18n_placeholder = ''  # TODO: implement if I18N implemented for Protocol model

        params = self.request.query_params
        if params:
            # owned by
            owned_by = params.get(OWNED_BY)
            if is_numeric_pk(owned_by):
                queryset = queryset.filter(owned_by=owned_by)
            else:
                # first try UUID-based input since UUID instantiation is the best way to error
                # check UUID input
                try:
                    queryset = queryset.filter(owned_by__uuid=owned_by)
                except Exception:
                    # if this wasn't a valid UUID, assume it's a regex for the username
                    queryset = _optional_regex_filter(params, queryset, 'owned_by__username',
                                                      self.OWNED_BY_QUERY_PARAM,
                                                      i18n_placeholder)

            # variant of
            variant_of = params.get(VARIANT_OF)
            if variant_of:
                queryset = queryset.filter(variant_of=variant_of)

            # default units
            default_units = params.get(DEFAULT_UNITS_QUERY_PARAM)
            if default_units:
                if is_numeric_pk(default_units):
                    queryset = queryset.filter(default_units=default_units)
                # first try UUID-based input since UUID instantiation is the best way to error
                # check UUID input
                try:
                    queryset = queryset.filter(default_units__uuid=default_units)
                except Exception:
                    # if this wasn't a valid UUID, assume it's a regex for the unit name

                    queryset = _optional_regex_filter(params, queryset,
                                                      'default_units__unit_name',
                                                      DEFAULT_UNITS_QUERY_PARAM,
                                                      i18n_placeholder)
            # categorization
            queryset = _optional_regex_filter(params, queryset, 'categorization',
                                              CATEGORIZATION_QUERY_PARAM, i18n_placeholder)

            # sort (based on name)
            sort = params.get(SORT_PARAM)
            if sort is not None:
                queryset = queryset.order_by(self.NAME_PROPERTY)

                if sort == REVERSE_SORT_VALUE:
                    queryset = queryset.reverse()

            queryset = _optional_regex_filter(params, queryset, self.NAME_PROPERTY,
                                              self.NAME_QUERY_PARAM, i18n_placeholder)

            queryset = _optional_timestamp_filter(queryset, self.request.query_params)

        return queryset


def _optional_regex_filter(query_params_dict, queryset, data_member_name, regex_param_name,
                           locale_param_name):
    """
    Implements consistent regular expression matching behavior for EDD's REST API. Applies
    default behaviors re: case-sensitivity to all regex-based searches in the REST API.
    :param queryset: the queryset to filter based on the regular expression parameter
    :param data_member_name the django model data member name to be filtered according to the
        regex, if present
    :param regex_param_name: the query parameter name REST API clients use to pass the regular
        expression used for the search
    :param locale_param_name: the query parameter name REST API clients use to pass the locale used
        to determine which strings the regular expression is tested against
    :return: the queryset, filtered using the regex, if available
    """
    # TODO: do something with locale, which we've at least forced clients to provide to simplify
    # future full i18n support

    regex_value = query_params_dict.get(regex_param_name)
    if not regex_value:
        return queryset

    case_sensitive_search = CASE_SENSITIVE_PARAM in query_params_dict
    search_type = 'regex' if case_sensitive_search else 'iregex'
    filter_param = '%(data_member_name)s__%(search_type)s' % {
        'data_member_name': data_member_name,
        'search_type': search_type
    }

    return queryset.filter(**{filter_param: regex_value})


class MetadataGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that supports view-only access to EDD's metadata groups.
    TODO: implement/confirm access controls for unsafe methods, then make this writable
    """
    queryset = MetadataGroup.objects.all()  # must be defined for DjangoModelPermissions
    serializer_class = MetadataGroupSerializer

    def list(self, request, *args, **kwargs):
        """
        Lists the metadata groups in EDD's database
        """


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    # TODO: allows unrestricted read access
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    """
    API endpoint that allows privileged users to get read-only information on the current set of
    EDD user accounts.
    """
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(self.kwargs['user'])


PAGING_PARAMETER_DESCRIPTIONS = """
            parameters:
               - name: page
                 type: integer
                 description: the number of the results page to return (starting with 1)


            responseMessages:
               - code: 401
                 message: Not authenticated
               - code: 403
                 message: Insufficient rights to call this procedure
               - code: 500 internal server error
    """


class StrainViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    # mixins.DestroyModelMixin,  TODO: implement & test later as a low priority
                    mixins.ListModelMixin,
                    GenericViewSet):
    """
    Defines the set of REST API views available for the base /rest/strain/ resource. Nested views
    are defined elsewhere (e.g. StrainStudiesView).
    """
    permission_classes = [ImpliedPermissions]

    # Note: queryset must be defined for DjangoModelPermissions in addition to get_queryset(). See
    # related  comment/URL above
    queryset = Strain.objects.none()

    serializer_class = StrainSerializer
    lookup_url_kwarg = BASE_STRAIN_URL_KWARG

    def get_object(self):
        """
        Overrides the default implementation to provide flexible lookup for Strain detail
        views (either based on local numeric primary key, or based on the strain UUID from ICE
        """
        queryset = self.get_queryset()

        # unlike the DRF example code: for consistency in permissions enforcement, just do all the
        # filtering in get_queryset() and pass empty filters here
        filters = {}
        obj = get_object_or_404(queryset, **filters)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        """
        Overrides the default implementation to provide:
        * flexible list view filtering based on a number of useful input parameters
        * flexible strain detail lookup by local numeric pk OR by UUID from ICE
        """

        logger.debug('Start %(class)s. %(method)s %(url)s' % {
            'class': self.__class__.__name__,
            'method': self.get_queryset.__name__,
            'url': self.request.path})

        # build a query, filtering by the provided user inputs (starting out unfiltered).
        # TODO: Strain has been recently updated to be an EDDObject.  We can reuse more code here than before, and
        # also likely take advantage of newer/more standard search features in optional_edd_object_filtering().
        # However, there are now two UUID's for a strain...
        query = Strain.objects.all()

        # if a strain UUID or local numeric pk was provided via the URL, get it
        identifier = None
        if self.kwargs:
            identifier = self.kwargs.get(self.lookup_url_kwarg)

            try:
                if is_numeric_pk(identifier):
                    query = query.filter(pk=int(identifier))
                else:
                    query = query.filter(registry_id=UUID(identifier))
            except ValueError:
                raise ParseError('URL identifier "%s" is neither a valid integer nor UUID' %
                                 identifier)
        # otherwise, we're searching strains, so filter them according to the provided params
        else:
            # parse optional query parameters
            query_params = self.request.query_params
            identifier = query_params.get(self.lookup_url_kwarg)
            local_pk_filter = query_params.get('pk')
            registry_id_filter = query_params.get(STRAIN_REGISTRY_ID)
            registry_url_regex_filter = query_params.get(STRAIN_REGISTRY_URL_REGEX)
            case_sensitive = query_params.get(STRAIN_CASE_SENSITIVE)
            name_filter = query_params.get(STRAIN_NAME)

            try:
                # if provided an ambiguously-defined unique ID for the strain, apply it based
                # on the format of the provided value
                if identifier:
                    if is_numeric_pk(identifier):
                        query = query.filter(pk=identifier)
                    else:
                        query = query.filter(registry_id=UUID(identifier))

                if local_pk_filter:
                    identifier = local_pk_filter
                    query = query.filter(pk=local_pk_filter)

                if registry_id_filter:
                    identifier = registry_id_filter
                    query = query.filter(registry_id=UUID(registry_id_filter))
            except ValueError:
                raise ParseError('Identifier %s is not a valid integer nor UUID' % identifier)

            if registry_url_regex_filter:
                if case_sensitive:
                    query = query.filter(registry_url__regex=registry_url_regex_filter)
                else:
                    query = query.filter(registry_url__iregex=registry_url_regex_filter)

            if name_filter:
                if case_sensitive:
                    query = query.filter(name__contains=name_filter)
                else:
                    query = query.filter(name__icontains=name_filter)

            query = _optional_regex_filter(query_params, query, 'name', STRAIN_NAME_REGEX, None)
            query = _optional_timestamp_filter(query, query_params)

        # filter results to ONLY the strains accessible by this user. Note that this may
        # prevent some users from accessing strains, depending on how EDD's permissions are set up,
        # but the present alternative is to create a potential leak of experimental strain names /
        # descriptions to potentially competing researchers that use the same EDD instance

        # if user is requesting to add / modify / delete strains, apply django.auth permissions
        # to determine access
        user = self.request.user
        http_method = self.request.method
        if http_method in HTTP_MUTATOR_METHODS:
            if not user.is_authenticated():
                logger.debug('User is not authenticated. Returning zero results')
                return Strain.objects.none()
            if user_has_admin_or_manage_perm(self.request, query):
                logger.debug('User %s has manage permissions for ')
                return query
            return Strain.objects.none()

        # if user is requesting to view one or more strains, allow either django auth permissions
        # or study permissions to determine whether or not the strain is visible to this user. If
        # the user has access to this study, they'll be able to view strain details in the UI.
        query = filter_for_study_permission(self.request, query, Strain, 'line__study__')
        logger.debug('StrainViewSet query count=%d' % len(query))
        return query

    def list(self, request, *args, **kwargs):
        """
            List strains the requesting user has access to.

            Strain access is defined by:

            1.  Study read access. A user has read access to strains in any study s/he has read
            access to.

            2.  Explicit strain permissions. Any user who has the add/update/delete permission to
            the strain class will have that level of access to strains, as well as implied read
            access to all of them.

            3.  Administrative access. System administrators always have full access to strains.

            ---
            responseMessages:
               - code: 400
                 message: Bad client request
               - code: 401
                 message: Unauthenticated
               - code: 403
                 message: Forbidden. User is authenticated but lacks the required permissions.
               - code: 500
                 message: Internal server error
            parameters:
               - name: page
                 paramType: query  # work django-rest-swagger breaking this in override
                 type: integer
                 description: The number of the results page to return (starting with 1)
               - name: page_size
                 paramType: query  # work django-rest-swagger breaking this in override
                 type: integer
                 description: "The requested maximum page size for results. May not be respected
                 by EDD if this value exceeds the server's maximum supported page size."
            """
        return super(StrainViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        View details of a single strain

        ---
            responseMessages:
               - code: 400
                 message: Bad client request
               - code: 401
                 message: Unauthenticated
               - code: 403
                 message: Forbidden. User is authenticated but lacks the required permissions.
               - code: 500
                 message: Internal server error
        """
        return super(StrainViewSet, self).retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new strain.
        ---
            responseMessages:
               - code: 400
                 message: Bad client request
               - code: 401
                 message: Unauthenticated
               - code: 403
                 message: Forbidden. User is authenticated but lacks the required permissions.
               - code: 500
                 message: Internal server error
        """
        # TODO: as a future improvement, limit strain creation input to only ICE part identifier
        #  (part ID, local pk, or UUID), except by apps with additional privileges (e.g. those
        # granted to ICE itself to update strain data for ICE-72).  For now, we can just limit
        # strain creation privileges to control consistency of newly-created strains (which
        # should be created via the UI in most cases anyway).
        return super(StrainViewSet, self).create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update all fields of an existing strain.
        ---
            responseMessages:
               - code: 400
                 message: Bad client request
               - code: 401
                 message: Unauthenticated
               - code: 403
                 message: Forbidden. User is authenticated but lacks the required permissions.
               - code: 404
                 message: Strain doesn't exist
               - code: 500
                 message: Internal server error
        """
        return super(StrainViewSet, self).update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
            Update only the provided fields of an existing strain.
            ---
                responseMessages:
                   - code: 400
                     message: Bad client request
                   - code: 401
                     message: Unauthenticated
                   - code: 403
                     message: Forbidden. User is authenticated but lacks the required permissions.
                   - code: 404
                     message: Strain doesn't exist
                   - code: 500
                     message: Internal server error
            """


HTTP_TO_STUDY_PERMISSION_MAP = {
    'POST': StudyPermission.WRITE,
    'PUT': StudyPermission.WRITE,
    'DELETE': StudyPermission.WRITE,
    'PATCH': StudyPermission.WRITE,
    'OPTIONS': StudyPermission.NONE,
    'HEAD': StudyPermission.READ,
    'GET': StudyPermission.READ,
}


def get_requested_study_permission(http_method):
    return HTTP_TO_STUDY_PERMISSION_MAP.get(http_method.upper())


# TODO: detail views should allow access to even inactive lines by default! need to add a list/detail-related param,
# follow through to clients, and then test!
def filter_by_active_status(queryset, active_status=QUERY_ACTIVE_OBJECTS_ONLY, query_prefix=''):
    """
    A helper method for queryset filtering based on a standard set of HTTP request
    parameter values that indicate whether EddObjects should be considered in the query based on
    their 'active' status.

    For a single object class A related to the ORM model class B returned from the query, a call to
    filter_by_active_status() will filter the query according to A's 'active' status. Note
    that this filtering by active status will result in the queryset returning one row for each
    relations of A to B, so clients will often want to use distinct() to limit the returned
    results.  A typical use of this method is to control which lines are considered
    in a query.

    Example 1 : Finding only active Lines. This is slightly more code than to just filter the
                query directly, but that wouldn't be standard across REST resource implementations.

    queryset = Line.objects.all()
    queryset = filter_by_active_status(queryset, active_status=ACTIVE_ONLY,
                                       query_prefix='').distinct()

    Example 2: Finding Strains associated with a Study by active lines

    queryset = Strain.objects.filter(line__study__pk=study_id)
    queryset = filter_by_active_status(queryset, active_status=ACTIVE_ONLY,
                                       query_prefix=('line__')).distinct()

    :param queryset: the base queryset to apply filtering to
    :param active_status: the HTTP request query parameter whose value implies the type of
    filtering to apply based on active status. If this isn't one of the recognized values,
    the default behavior is applied, filtering out inactive objects. See
    constants.ACTIVE_STATUS_OPTIONS.
    :param query_prefix: an optional keyword prefix indicating the relationship of the filtered
    class to the model we're querying (see examples above)
    :return: the input query, filtered according to the parameters
    """
    active_status = active_status.lower()

    # just return the parameter if no extra filtering is required
    if active_status == QUERY_ANY_ACTIVE_STATUS:
        return queryset

    # construct an ORM query keyword based on the relationship of the filtered model class to the
    # Django model class being queried. For example 1 above, when querying Line.objects.all(),
    # we prepend '' and come up with Q(active=True). For example 2, when querying
    # Strain, we prepend 'line__' and get Q(line__active=True)
    orm_query_keyword = '%sactive' % query_prefix
    # return requested status, or active objects only if input was bad
    active_value = (active_status != QUERY_INACTIVE_OBJECTS_ONLY)

    active_criterion = Q(**{orm_query_keyword: active_value})
    return queryset.filter(active_criterion)


class StudyViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   # TODO: implement & test later as a low priority...study deletion via the
                   # API should maybe only mark studies as "disabled" if they have data (or maybe
                   # should require an override parameter to actually delete.
                   # mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
    """
    API endpoint that provides access to studies, subject to user/role read access
    controls. Note that some privileged 'manager' users may have access to the base study name,
    description, etc, but not to the contained experiment description or data.
    """
    serializer_class = StudySerializer
    contact = StringRelatedField(many=False)
    permission_classes = [StudyResourcePermissions]

    # TODO: uncomment, set to "id" for clarity, and retest nested resources (after unit testing)
    # lookup_url_kwarg = STUDY_URL_KWARG

    def get_object(self):
        """
        Overrides the default implementation to provide flexible lookup for Study detail
        views (either based on local numeric primary key, slug, or UUID
        """
        queryset = self.get_queryset()

        # unlike the DRF example code: for consistency in permissions enforcement, just do all the
        # filtering in get_queryset() and pass empty filters here
        filters = {}
        obj = get_object_or_404(queryset, **filters)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):

        params = self.request.query_params
        study_id = self.kwargs.get('pk', None)
        return build_study_query(self.request, params, identifier=study_id)

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not Study.user_can_create(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        return super(StudyViewSet, self).create(request, *args, **kwargs)


def build_study_query(request, query_params, identifier=None, skip_study_manage_perms=False):
    """
    A helper method for constructing a Study QuerySet while consistently applying Study permissions.
    :param skip_study_manage_perms: True to disallow access to the study based on class-level django.util.auth
        permissions that only grant permission to the base study details (e.g. name, description, contact) rather than
        the contained data.  Use False to apply only Study-specific user permissions, e.g. when accessing nested study
        resources like Lines, Measurements, etc.
    """
    study_query = Study.objects.all()

    # if client provided any identifier, filter based on it. Note that since studies have a slug
    # that most other EddObjects don't have, we do our id filtering up front rather than using EddObject filtering. We
    # also use int/UUID constructors to guarantee that input format checking is performed up front at queryset
    # construction time (400 error) rather than evaluation time (500 error)
    if identifier:
        # test whether this is an integer pk
        found_identifier_format = False
        try:
            study_query = study_query.filter(pk=int(identifier))
            found_identifier_format = True
        except ValueError:
            pass

        # if format not found, try UUID
        if not found_identifier_format:
            try:
                study_query = study_query.filter(uuid=UUID(identifier))
                found_identifier_format = True
            except ValueError:
                pass

        # otherwise assume it's a slug
        if not found_identifier_format:
            study_query = study_query.filter(slug=identifier)

    # apply standard filtering options, but skip ID-based filtering we've just finished
    study_query = optional_edd_object_filtering(query_params, study_query, skip_id_filtering=True)

    # apply study permissions
    enabling_manage_perms = [] if skip_study_manage_perms else None
    study_query = filter_for_study_permission(request, study_query, Study, '',
                                              enabling_manage_permissions=enabling_manage_perms)

    return study_query


def optional_edd_object_filtering(params, query, skip_id_filtering=False, identifier_override=None):
    """
    A helper method to perform filtering on standard EDDObject fields
    :param params:
    :param query:
    :param skip_id_filtering:
    :param identifier_override:
    :return:
    """
    # filter results based on the provided ID (can take multiple forms). Note: we purposefully use int/UUID
    # constructors here to force errors to occur at query *construction* time rather than *evaluation* time.
    # format checks deferred until evaluation will result in 500 errors rather than more appropriate 400's
    if not skip_id_filtering:
        helpful_uuid_err = 'Invalid hexidecimal UUID string "%s"'
        # if an identifier came from another source (e.g. query URL) use that one
        if identifier_override:
            logger.debug('Filtering query for overridden identifier "%s"' % identifier_override)
            # test whether this is an integer pk
            try:
                query = query.filter(pk=int(identifier_override))
            except ValueError:
                try:
                    query = query.filter(uuid=UUID(identifier_override))
                except ValueError as err:
                    raise ParseError(helpful_uuid_err % identifier_override)  # provide good HTTP 400 errs to client

        # otherwise, look for identifiers in the search params
        else:
            identifier = params.get('pk')
            if identifier:
                try:
                    query = query.filter(pk=int(identifier))
                except ValueError:
                    raise ParseError(helpful_uuid_err % identifier)

            identifier = params.get('uuid')
            if identifier:
                try:
                    query = query.filter(uuid=UUID(identifier))
                except ValueError:
                    raise ParseError(helpful_uuid_err % identifier)

    # apply optional name-based filtering
    query = _optional_regex_filter(params, query, 'name', NAME_REGEX_PARAM, None, )

    # apply optional description-based filtering
    query = _optional_regex_filter(params, query, 'description', DESCRIPTION_REGEX_PARAM,
                                   None, )

    # filter for active status, or apply the default of only returning active objects.
    # if accessing a detail view, default to returning the result regardless of active status since it was specifically
    # requested
    active_status = params.get(ACTIVE_STATUS_PARAM, QUERY_ANY_ACTIVE_STATUS if identifier_override
                               else ACTIVE_STATUS_DEFAULT)
    query = filter_by_active_status(query, active_status=active_status)

    # apply timestamp_based filtering
    query = _optional_timestamp_filter(query, params)

    # apply optional metadata lookups supported by Django's HStoreField.  Since we trust
    # django to apply security checks, for starters we'll expose the HStoreField query
    # parameters to clients more-or-less directly.  This is necessary to help support
    # comparisons that our current lack of metadata validation makes difficult, e.g. growth
    #  temp > X.  See EDD-771, and possibly other tickets linked to EDD-438. If needed,
    # we can add in abstractions later to help with this....e.g. expose an
    # artificially-added 'lt' operator.
    meta_comparisons = params.get(META_SEARCH_PARAM)

    if not meta_comparisons:
        return query

    if isinstance(meta_comparisons, list):
        comparison_count = len(meta_comparisons)
        for index, comparison in enumerate(meta_comparisons):
            query = _filter_for_metadata(query, comparison, index+1, comparison_count)
    else:
        query = _filter_for_metadata(query, meta_comparisons, 1, 1)

    return query


def _filter_for_metadata(query, meta_comparison, comparison_num, comparison_count):
    meta_key = meta_comparison.get(META_KEY_PARAM, None)
    meta_operator = meta_comparison.get(META_OPERATOR_PARAM, None)
    metadata_test = meta_comparison.get(META_VALUE_PARAM, None)

    # tolerate numeric values used for comparison.  They must be converted to strings to work
    # for comparison against Postgres' HStoreField. Note that keys will automatically be converted
    # to strings by JSON serialization, regardless of what clients specify. Alternative is to raise
    # or work around a ProgrammingError at query evaluation time
    if isinstance(metadata_test, numbers.Number):
        metadata_test = str(metadata_test)
    elif isinstance(metadata_test, list):
        for index, item in enumerate(metadata_test):
            if isinstance(item, numbers.Number):
                metadata_test[index] = str(item)
    elif isinstance(metadata_test, dict):
        for key, value in metadata_test.iteritems():
            if isinstance(value, numbers.Number):
                metadata_test[key] = str(value)

    comparison_desc = (('%s (comparison %d): ' % (META_SEARCH_PARAM, comparison_num))
                       if comparison_count > 1 else ('%s: ' % META_SEARCH_PARAM))

    # Do some error checking for consistent definition of parameters.  Error messages defined
    # here should be a very helpful supplement to those generated by Django when we attempt the
    # query.  Clients shouldn't have to know or care how this is implemented, and should get
    #  transparent error messages.

    if not meta_operator:
        raise ValidationError('%(comp)s"%(op)s" is required' % {
            'comp': comparison_desc,
            'op': META_OPERATOR_PARAM})

    if meta_operator in NON_KEY_DJANGO_HSTORE_COMPARISONS or meta_operator.startswith('keys'):
        if meta_key:
            raise ValidationError("""""%(comp)s%(key)s isn't allowed for operator "%(op)s.
            Use "%(value)s" instead.""""" % {
                'comp': comparison_desc, 'key': META_KEY_PARAM, 'op': meta_operator,
                'value': META_VALUE_PARAM
            })

    # elif not meta_key:
    #     raise ValidationError('%(comp)s"%(key)s" parameter is required for operator "%(op)s"' % {
    #         'comp': comparison_desc,
    #         'key':  META_KEY_PARAM,
    #         'op':   meta_operator,
    #     })

    if not metadata_test:
        # TODO: update message to simplify if current logic is proven correct by tests
        raise ValidationError(['%(comp)sParameters are inconsistent. %(test)s is required when '
                               '%(op)s is provided.' % {
                                   'comp': comparison_desc,
                                   'key':  META_KEY_PARAM,
                                   'op':   META_OPERATOR_PARAM,
                                   'test': metadata_test,
                               }])
    prefix = 'meta_store__'
    comparison = meta_operator
    if meta_key:
        prefix = 'meta_store__%s' % meta_key
        comparison = '__%s' % meta_operator if meta_operator != '=' else ''

    filter_key = '%(prefix)s%(comparison)s' % {
        'prefix': prefix,
        'comparison': comparison,
    }
    filter_dict = {filter_key: metadata_test}

    # TODO: remove print stmt
    print('Metadata filter %d of %d: %s' % (comparison_num, comparison_count, str(filter_dict)))

    # TODO: test/investigate/wrap? raised Errors...here or when queryset is actually executed?
    return query.filter(**filter_dict)


# TODO: take study active status into account...unlikely in most cases that inactive studies should
# grant access to the contained lines/metadata/measurements/etc
def filter_for_study_permission(request, query, result_model_class, study_keyword_prefix,
                                enabling_manage_permissions=USE_STANDARD_PERMISSIONS,
                                requested_study_permission_override=None):
    """
        A helper method to filter a Queryset to return only results that the requesting user
        should have access to, based on django.auth permissions and on explicitly-configured
        main.models.StudyPermissions. Note the assumption that the requested resource is unique
        to the study (e.g. Lines).
        :param request: the HttpRequest to access a study-related resource
        :param query: the queryset as defined by the request (with permissions not yet enforced)
        :result_model_class: the Django model class returned by the QuerySet. If the user has
        class-level django.contrib.auth appropriate permissions to view/modify/create objects of
        this type, access will be granted regardless of configured Study-level permissions.
        :param enabling_manage_permissions: a list of django.util.auth permission codes
        that optionally overrides the default set of permissions that would otherwise determine
        class-level access to all of the results based on request.method. If None, the default
        permissions will be applied, or django.contrib.auth permissions will be ignored if an empty list is provided.

     """

    # never show anything to un-authenticated users
    user = request.user
    if (not user) or not user.is_authenticated():
        logger.debug('User %s is not authenticated' % user)
        return result_model_class.objects.none()

    if requested_study_permission_override is None:
        requested_permission = get_requested_study_permission(request.method)
    else:
        requested_permission = requested_study_permission_override

    # if user role (e.g. admin) grants access to all studies, we can expose all strains
    # without additional queries
    has_role_based_permission = (requested_permission == StudyPermission.READ and
                                 Study.user_role_can_read(user))
    if has_role_based_permission:
        return query

    # test whether explicit "manager" permissions allow user to access all results without
    # having to drill down into case-by-case study or study/line/strain relationships that would
    # grant access to a subset of results
    has_explicit_manage_permission = False
    if enabling_manage_permissions is None:
        enabling_manage_permissions = (
            ImpliedPermissions.get_standard_enabling_permissions(
                    request.method, result_model_class))

    for manage_permission in enabling_manage_permissions:
        if user.has_perm(manage_permission):
            has_explicit_manage_permission = True
            logger.debug('User %(user)s has explicit permission to %(requested_perm)s '
                         'all %(manage_perm_class)s objects, implied via the "%(granting_perm)s" '
                         'permission' % {
                             'user':              user.username,
                             'manage_perm_class': result_model_class.__class__.__name__,
                             'requested_perm':    requested_permission,
                             'granting_perm':     manage_permission,
                         })
            break

    if has_explicit_manage_permission:
        return query

    # if user has no global permissions that grant access to all results , filter
    # results to only those exposed in studies the user has read/write
    # access to. This is significantly more expensive, but exposes the same data available
    # via the UI. Where possible, we should encourage clients to access nested study resources via
    # /rest/studies/X/Y to avoid these joins.

    # if user is only requesting read access to the strain, construct a query that
    # will infer read permission from the existing of either read or write
    # permission
    if requested_permission == StudyPermission.READ:
        requested_permission = StudyPermission.CAN_VIEW
    user_permission_q = Study.user_permission_q(user, requested_permission,
                                                keyword_prefix=study_keyword_prefix)
    query = query.filter(user_permission_q).distinct()
    return query


NUMERIC_PK_PATTERN = re.compile('^\d+$')

# Notes on DRF nested views:
# lookup_url_kwargs doesn't seem to be used/respected by nested routers in the same way as plain
# DRF - see StrainStudiesView for an example that works, but isn't clearly the most clear yet


class StrainStudiesView(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows read-only access to the studies a given strain is used in (subject to
    user/role read access privileges on the studies).
    """
    serializer_class = StudySerializer
    lookup_url_kwarg = 'study_pk'

    def get_object(self):
        """
        Overrides the default implementation to provide flexible lookup for nested strain
        views (either based on local numeric primary key, or based on the strain UUID from ICE
        """
        # unlike the example, just do all the filtering in get_queryset() for consistency
        filters = {}
        queryset = self.get_queryset()

        obj = get_object_or_404(queryset, **filters)
        # verify class-level strain access. study permissions are enforced in get_queryset()
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        kwarg = '%s_%s' % (STRAIN_NESTED_RESOURCE_PARENT_PREFIX, BASE_STRAIN_URL_KWARG)
        # get the strain identifier, which could be either a numeric (local) primary key, or a UUID
        strain_id = self.kwargs.get(kwarg)

        # figure out which it is
        strain_pk = strain_id if is_numeric_pk(strain_id) else None
        strain_uuid = strain_id if not strain_pk else None

        params = self.request.query_params

        line_active_status = self.request.query_params.get(
            ACTIVE_STATUS_PARAM, ACTIVE_STATUS_DEFAULT
        )
        user = self.request.user

        # only allow superusers through, since this is strain-related data that should only be
        # accessible to sysadmins. Also allows us to potentially avoid expensive joins to check for
        # per-study user/group permissions (though we've included below for the moment for safety)
        if not user.is_superuser:
            #  TODO: user group / merge in recent changes / throw PermissionsError or whatever
            return Response(status=status.HTTP_403_FORBIDDEN)

        study_pks_query = None
        if strain_pk:
            study_pks_query = Line.objects.filter(strains__pk=strain_pk)
        else:
            study_pks_query = Line.objects.filter(strains__registry_id=strain_uuid)
        study_pks_query = filter_by_active_status(
                study_pks_query, active_status=line_active_status).values_list(
                'study__pk').distinct()  # distict() needed bc of line active status filtering
        studies_query = Study.objects.filter(pk__in=study_pks_query)

        study_pk = self.kwargs.get(self.lookup_url_kwarg)
        if study_pk:
            studies_query = studies_query.filter(pk=study_pk)

        studies_query = _optional_timestamp_filter(studies_query, params)

        # enforce EDD's custom access controls for readability of the associated studies. Note:
        # at present this isn't strictly necessary because of the sysadmin check above but best
        # to enforce programatically in case the implementation of Study's access controls
        # changes later on
        if not Study.user_role_can_read(user):
            study_user_permission_q = Study.user_permission_q(user, StudyPermission.READ,
                                                              keyword_prefix='line__study__')
            studies_query = studies_query.filter(study_user_permission_q)
        # required by both line activity and studies permissions queries
        studies_query = studies_query.distinct()

        return studies_query


class StudyStrainsView(viewsets.ReadOnlyModelViewSet):
    """
        API endpoint that allows read-only viewing the unique strains used within a specific study
    """
    serializer_class = StrainSerializer
    STUDY_URL_KWARG = '%s_pk' % STUDIES_RESOURCE_NAME
    lookup_url_kwarg = 'strain_pk'

    # override

    def get_object(self):
        """
            Overrides the default implementation to provide flexible lookup for nested strain
            views (either based on local numeric primary key, or based on the strain UUID from ICE
            """
        filters = {}  # unlike the example, just do all the filtering in get_queryset() for
        # consistency
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, **filters)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        # TODO: this query takes way too long to complete (at least in
        # local tests on a laptop) for users who are granted read
        # permission on a single study, but have no superuser basis for accessing it . Performance
        # problem appears to be related to study_user_permission_q and related joins. Consider
        # using Solr to index in addition to optimizing the query.
        logger.debug('%(class)s.%(method)s: kwargs = %(kwargs)s' % {
            'class':  StudyStrainsView.__name__,
            'method': self.get_queryset.__name__,
            'kwargs': self.kwargs
        })

        # extract URL keyword arguments
        study_id = self.kwargs[self.STUDY_URL_KWARG]

        study_id_is_pk = is_numeric_pk(study_id)
        line_active_status = self.request.query_params.get(LINE_ACTIVE_STATUS_PARAM,
                                                           ACTIVE_STATUS_DEFAULT)
        user = self.request.user

        # build the query, enforcing EDD's custom study access controls. Normally we'd require
        # sysadmin access to view strains, but the names/descriptions of strains in the study
        # should be visible to users with read access to a study that measures them
        study_user_permission_q = Study.user_permission_q(user, StudyPermission.READ,
                                                          keyword_prefix='line__study__')
        if study_id_is_pk:
            strain_query = Strain.objects.filter(study_user_permission_q, line__study__pk=study_id)
        else:
            logger.error("Non-numeric study IDs aren't supported.")
            return Strain.objects.none()

        strain_id = self.kwargs.get(self.lookup_url_kwarg)
        if strain_id:
            strain_id_is_pk = is_numeric_pk(strain_id)

            if strain_id_is_pk:
                strain_query = strain_query.filter(pk=strain_id)
            else:
                strain_query = strain_query.filter(registry_id=strain_id)

        # filter by line active status, applying the default (only active lines)
        strain_query = filter_by_active_status(strain_query, line_active_status,
                                               query_prefix='line__')
        # required by both study permission query and line active filters above
        strain_query = strain_query.distinct()

        return strain_query


class StudyLinesView(viewsets.ReadOnlyModelViewSet):  # LineView(APIView):
    """
        API endpoint that allows lines within a study to be searched, viewed, and edited.
    """
    serializer_class = LineSerializer
    lookup_url_kwarg = 'line_pk'
    STUDY_URL_KWARG = '%s_pk' % STUDIES_RESOURCE_NAME

    def get_object(self):
        """
        Overrides the default implementation to provide flexible lookup for Study Lines (either based on local numeric
        primary key, or based on the strain UUID from ICE
        """
        queryset = self.get_queryset()

        # unlike the DRF example code: for consistency in permissions enforcement, just do all the
        # filtering in get_queryset() and pass empty filters here
        filters = {}
        obj = get_object_or_404(queryset, **filters)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        logger.debug('in %(class)s.%(method)s' % {
            'class': StudyLinesView.__name__,
            'method': self.get_queryset.__name__
        })

        if not self.request.user.is_authenticated():
            raise NotAuthenticated()

        query_params = self.request.query_params

        # load / check study permissions rather than using expensive joins that include Study/StudyPermission/Line
        study_id = self.kwargs[self.STUDY_URL_KWARG]
        study_query_params = {ACTIVE_STATUS_PARAM: QUERY_ANY_ACTIVE_STATUS}  # ignore active status for enclosing study
        study = build_study_query(self.request, study_query_params, identifier=study_id, skip_study_manage_perms=True)
        if not study:
            logger.debug('Study %s not found' % study_id)
            raise NotFound('Study %s not found' % study_id)

        logger.debug('Querying lines in study %s' % study_id)
        queryset = optional_edd_object_filtering(query_params,
                                                 Line.objects.filter(study__pk=study.get().pk),
                                                 identifier_override=self.kwargs.get(self.lookup_url_kwarg))
        return queryset

    # def create(self, request, *args, **kwargs):
    #     ##############################################################
    #     # enforce study write privileges
    #     ##############################################################
    #     study_pk = self.kwargs[self.STUDY_URL_KWARG]
    #     user = self.request.user
    #     StudyLinesView._test_user_write_access(user, study_pk)
    #     # if user has write privileges for the study, use parent implementation
    #     return super(StudyLinesView, self).create(request, *args, **kwargs)
    #
    # def update(self, request, *args, **kwargs):
    #     ##############################################################
    #     # enforce study write privileges
    #     ##############################################################
    #     study_pk = self.kwargs[self.STUDY_URL_KWARG]
    #     user = self.request.user
    #     StudyLinesView._test_user_write_access(user, study_pk)
    #     # if user has write privileges for the study, use parent implementation
    #     return super(StudyLinesView, self).update(request, *args, **kwargs)
    #
    # def destroy(self, request, *args, **kwargs):
    #     ##############################################################
    #     # enforce study write privileges
    #     ##############################################################
    #     study_pk = self.kwargs[self.STUDY_URL_KWARG]
    #     user = self.request.user
    #     StudyLinesView._test_user_write_access(user, study_pk)
    #     # if user has write privileges for the study, use parent implementation
    #     return super(StudyLinesView, self).destroy(request, *args, **kwargs)


class NotImplementedException(APIException):
    status_code = 500
    default_detail = 'Not yet implemented'


def _optional_timestamp_filter(queryset, query_params):
    """
    For any EddObject-derived model object, creates and returns an updated queryset that's
    optionally filtered by creation or update timestamp. Note that in both cases the start bound
    is inclusive and the end is exclusive.
    @:raise ParseError if the one of the related query parameters was provided, but was
    improperly formatted
    """
    query_param_name, value = None, None
    try:
        # filter by creation timestamp
        created_after_value = query_params.get(CREATED_AFTER_PARAM, None)
        created_before_value = query_params.get(CREATED_BEFORE_PARAM, None)
        if created_after_value:
            query_param_name, value = CREATED_AFTER_PARAM, created_after_value
            queryset = queryset.filter(created__mod_time__gte=created_after_value)
        if created_before_value:
            query_param_name, value = CREATED_BEFORE_PARAM, created_before_value
            queryset = queryset.filter(created__mod_time__lt=created_before_value)

        # filter by last update timestamp
        updated_after = query_params.get(UPDATED_AFTER_PARAM, None)
        updated_before = query_params.get(UPDATED_BEFORE_PARAM, None)
        if updated_after:
            query_param_name, value = UPDATED_AFTER_PARAM, updated_after
            queryset = queryset.filter(updated__mod_time__gte=updated_after)
        if updated_before:
            query_param_name, value = UPDATED_BEFORE_PARAM, updated_before
            queryset = queryset.filter(updated__mod_time__lt=updated_before)

    # if user provided a date in a format Django doesn't understand,
    # re-raise in a way that makes the client error apparent
    except TypeError:
        raise ParseError(detail='%(param)s %(value)s is not a valid date/time.' % {
            'param': query_param_name,
            'value': value,
        })

    return queryset


def build_lines_query(request, query_params, identifier=None,
                      enabling_manage_permissions=USE_STANDARD_PERMISSIONS,
                      requested_study_permission_override=None):
    query = Line.objects.all()

    # filter by common EDDObject characteristics
    query = optional_edd_object_filtering(query_params, query, identifier_override=identifier)

    # apply study and django.contrib.auth permissions
    query = filter_for_study_permission(
            request, query, Line, 'study__',
            enabling_manage_permissions=enabling_manage_permissions,
            requested_study_permission_override=requested_study_permission_override)

    logger.debug('Found %d lines' % len(query))  # TODO: remove debug stmt

    return query


class SearchViewSet(GenericViewSet):
    """
    A generic search view that uses code from other API resources to enforce permissions and query
    results based on the requested result type.
    """
    # TODO: Remove/simplify if no additional permissions classes are used during API implementation
    permissions_lookup = {
        SEARCH_TYPE_LINES:   (ImpliedPermissions,),
        SEARCH_TYPE_MEASUREMENT_UNITS: (ImpliedPermissions,),
        SEARCH_TYPE_METADATA_TYPES: (ImpliedPermissions,),
        SEARCH_TYPE_PROTOCOLS: (ImpliedPermissions,),
        SEARCH_TYPE_STUDIES: (ImpliedPermissions,),
    }

    queryset_lookup = {
        SEARCH_TYPE_LINES: build_lines_query,
        SEARCH_TYPE_MEASUREMENT_UNITS: build_measurement_units_query,
        SEARCH_TYPE_METADATA_TYPES: build_metadata_type_query,
        SEARCH_TYPE_STUDIES: build_study_query,
    }

    serializer_lookup = {
        SEARCH_TYPE_LINES: LineSerializer,
        SEARCH_TYPE_MEASUREMENT_UNITS: MeasurementUnitSerializer,
        SEARCH_TYPE_METADATA_GROUPS: MetadataGroupSerializer,
        SEARCH_TYPE_METADATA_TYPES: MetadataTypeSerializer,
        SEARCH_TYPE_PROTOCOLS: ProtocolSerializer,
        SEARCH_TYPE_STRAINS: StrainSerializer,
        SEARCH_TYPE_STUDIES: StudySerializer,
    }

    study_permission_controlled_types = ('lines', 'strains', 'measurements')

    lookup_url_kwarg = 'id'

    def __init__(self, **kwargs):
        super(SearchViewSet, self).__init__(**kwargs)
        self.request_params = None
        self.search_type = None

    def create(self, request, *args, **kwargs):
        """
             Required method name to get benefits of supporting ViewSet / Router code, but actually
             just handles a POST request in this case
        """

        if not request.user.is_authenticated():
            raise NotAuthenticated()

        # code pasted/modified from ListModelMixin to implement pagination / asymmetric
        # serialization (input format doesn't match output for search)
        queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def initialize_request(self, request, *args, **kwargs):
        """
            Overrides the inherited 'request' attribute to add request body parsing / cache.
            Prevents get_queryset() and get_permissions() from having to parse the request body
            more than once.
        """
        result = super(SearchViewSet, self).initialize_request(request, args, kwargs)
        if not request.body:
            valid_values = ('"%s"' % val for val in self.permissions_lookup.viewkeys() &
                            self.queryset_lookup.viewkeys() &
                            self.serializer_lookup.viewkeys())
            raise ValidationError('No JSON search parameters were provided.  At a minimum, '
                                  '"%(type)s" is required. Valid %(type)s values are %(values)s' %
                                  {
                                      'type': SEARCH_TYPE_PARAM,
                                      'values': ', '.join(valid_values),
                                  })

        self.request_params = json.loads(request.body)
        self.search_type = self.request_params.get(SEARCH_TYPE_PARAM, None)
        if not self.search_type:
            raise ValidationError('%s is a required parameter' % SEARCH_TYPE_PARAM)

        return result

    def get_queryset(self):
        request_params = self.request_params
        search_type = self.search_type

        queryset_function = self.queryset_lookup.get(search_type)

        if not queryset_function:
            queryset_lookup = self.queryset_lookup
            raise ValidationError('%(search_type)s is not a supported value of %(param_name)s. '
                                  'Valid values are %(valid_values)s'
                                  % {
                                        'search_type': search_type,
                                        'param_name': SEARCH_TYPE_PARAM,
                                        'valid_values': ', '.join([
                                            '"%s"' % key for key in queryset_lookup.iterkeys()])
                                  })

        identifier = request_params.get('pk', request_params.get('uuid'))

        # execute the query function.  if result permissions are derived from study permissions,
        # override the default behavior of treating a POST request as requesting mutator permission
        if search_type in self.study_permission_controlled_types:
            queryset = queryset_function(
                    self.request, request_params, identifier=identifier,
                    requested_study_permission_override=StudyPermission.CAN_VIEW)
        else:
            queryset = queryset_function(self.request, request_params, identifier=identifier, )

        logger.debug('Query created by %(function)s is:\n%(query)s' % {
            'function': str(queryset_function),
            'query': queryset.query, })
        return queryset

    def get_permissions(self):
        """
        Overrides the default get_permissions() to delegate permissions to the appropriate class
        based on which Django model class we're searching.  Note that we also have to override the
        default django.util.auth permissions assumed in the delegated classes since for search
        we're using HTTP POST to return results normally provided by GET.
        :return:
        """

        search_class = self.search_type
        permissions_classes = self.permissions_lookup.get(search_class)
        if not permissions_classes:
            raise ValidationError('"%(type)s" is not a valid value for %(type_param)s. Valid '
                                  'values are %(valid_values)s' % {
                                      'type':         search_class,
                                      'type_param':   SEARCH_TYPE_PARAM,
                                      'valid_values': ', '.join(self.permissions_lookup.keys())
                                  })
        logger.debug('Delegating permissions enforcement to permissions classes: %s'
                     % ', '.join([str(perm_class) for perm_class in permissions_classes]))

        # alter standard application of POST since search uses HTTP POST, but applies permissions
        # normally applied to GET requests
        permissions_instances = (permission_class() for permission_class in permissions_classes)
        for permissions_instance in permissions_instances:

            if isinstance(permissions_instance, ImpliedPermissions):
                permissions_instance.django_perms_map['POST'] = (
                    ImpliedPermissions._AUTH_IMPLICIT_VIEW_PERMISSION)
                permissions_instance.method_to_inferred_perms_map['POST'] = (
                    ImpliedPermissions.QS_INFERRED_VIEW_PERMISSION)

        return permissions_instances

    def get_serializer_class(self):
        """
        Overrides the parent implementation to provide serialization that's dynamically determined
        by the requested result type
        """

        serializer = self.serializer_lookup.get(self.search_type, None)
        if not serializer:
            raise NotImplementedError('No serializer is defined for %(param)s "%(value)s"' % {
                'param': SEARCH_TYPE_PARAM,
                'value': self.search_type,
            })

        return serializer

def not_found_view(request):
    return JsonResponse({'status_code': 404,
                         'error': 'Requested resource "%s" was not found' % request.request.build_absolute_uri()})

# TODO: remove following testing of the generic SearchViewSet...in particular, check related
# fields defined here and how they respond in the generic search. It's been along time since
# this code was implemented.
# class SearchLinesViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     API endpoint that allows Lines to we viewed or edited.
#     TODO: add edit/create capability back in, based on study-level permissions.
#     TODO: control view on the basis of study permissions
#     """
#     queryset = Line.objects.all()  # TODO: strange that this appears required. Remove?
#     serializer_class = LineSerializer
#     contact = StringRelatedField(many=False)
#     experimenter = StringRelatedField(many=False)
#     permission_classes = [ModelImplicitViewOrResultImpliedPermissions]
#
#     def get_queryset(self):
#         params = self.request.query_params
#
#         id = self.kwargs.get('pk', None)
#         return build_lines_query(self.request, params, identifier=id)
