# coding: utf-8
#
# Copyright 2020 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Service layer for handling user-authentication with GAE's built-in system."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import datetime
import http.cookies

from core.domain import auth_domain
from core.platform import models
import python_utils

from google.appengine.api import users

auth_models, = models.Registry.import_models([models.NAMES.auth])

transaction_services = models.Registry.import_transaction_services()


def establish_auth_session(unused_request, unused_response):
    """Sets login cookies to maintain a user's sign-in session.

    Args:
        unused_request: webapp2.Request. Unused because App Engine handles user
            authentication implicitly.
        unused_response: webapp2.Response. Unused because App Engine handles
            user authentication implicitly.
    """
    pass


def destroy_auth_session(response):
    """Clears login cookies from the given response headers.

    Args:
        response: webapp2.Response. Response to clear the cookies from.
    """
    # App Engine sets the ACSID cookie for http:// and the SACSID cookie
    # for https:// . We just unset both below. We also unset dev_appserver_login
    # cookie used in local server.
    for cookie_name in (b'ACSID', b'SACSID', b'dev_appserver_login'):
        cookie = http.cookies.SimpleCookie()
        cookie[cookie_name] = ''
        cookie[cookie_name]['expires'] = (
            datetime.datetime.utcnow() - datetime.timedelta(days=1)
        ).strftime('%a, %d %b %Y %H:%M:%S GMT')
        response.headers.add_header(*cookie.output().split(b': ', 1))


def get_auth_claims_from_request(unused_request):
    """Authenticates the request and returns claims about its authorizer.

    Args:
        unused_request: webapp2.Request. The HTTP request to authenticate.
            Unused because Google AppEngine handles user authentication
            internally.

    Returns:
        AuthClaims|None. Claims about the currently signed in user. If no user
        is signed in, then returns None.

    Raises:
        InvalidAuthSessionError. The request contains an invalid session.
        StaleAuthSessionError. The cookie has lost its authority.
    """
    gae_user = users.get_current_user()
    if gae_user is not None:
        return auth_domain.AuthClaims(
            gae_user.user_id(), gae_user.email(), users.is_current_user_admin())
    return None


def mark_user_for_deletion(user_id):
    """Marks the user, and all of their auth associations, as deleted.

    Args:
        user_id: str. The unique ID of the user whose associations should be
            deleted.
    """
    assoc_by_user_id_model = (
        auth_models.UserAuthDetailsModel.get(user_id, strict=False))

    if assoc_by_user_id_model is not None:
        assoc_by_user_id_model.deleted = True
        assoc_by_user_id_model.update_timestamps()
        assoc_by_user_id_model.put()

    assoc_by_auth_id_model = (
        auth_models.UserIdentifiersModel.get_by_user_id(user_id)
        if assoc_by_user_id_model is None else
        auth_models.UserIdentifiersModel.get(
            assoc_by_user_id_model.gae_id, strict=False))

    if assoc_by_auth_id_model is not None:
        assoc_by_auth_id_model.deleted = True
        assoc_by_auth_id_model.update_timestamps()
        assoc_by_auth_id_model.put()


def delete_external_auth_associations(unused_user_id):
    """Deletes all associations that refer to the user outside of Oppia.

    There are no associations to GAE models managed outside of Oppia.

    Args:
        unused_user_id: str. The unique ID of the user whose associations should
            be deleted.
    """
    pass


def verify_external_auth_associations_are_deleted(unused_user_id):
    """Returns true if and only if we have successfully verified that all
    external associations have been deleted.

    There are no associations to GAE models managed outside of Oppia, so always
    returns True.

    Args:
        unused_user_id: str. The unique ID of the user whose associations should
            be checked.

    Returns:
        bool. True if and only if we have successfully verified that all
        external associations have been deleted.
    """
    return True


def get_auth_id_from_user_id(user_id):
    """Returns the auth ID associated with the given user ID.

    Args:
        user_id: str. The user ID.

    Returns:
        str|None. The auth ID associated with the given user ID, or None if no
        association exists.
    """
    assoc_by_user_id_model = (
        auth_models.UserAuthDetailsModel.get(user_id, strict=False))
    return (
        None if assoc_by_user_id_model is None else
        assoc_by_user_id_model.gae_id)


def get_multi_auth_ids_from_user_ids(user_ids):
    """Returns the auth IDs associated with the given user IDs.

    Args:
        user_ids: list(str). The user IDs.

    Returns:
        list(str|None). The auth IDs associated with each of the given user IDs,
        or None for associations which don't exist.
    """
    return [
        None if model is None else model.gae_id
        for model in auth_models.UserAuthDetailsModel.get_multi(user_ids)
    ]


def get_user_id_from_auth_id(auth_id):
    """Returns the user ID associated with the given auth ID.

    Args:
        auth_id: str. The auth ID.

    Returns:
        str|None. The user ID associated with the given auth ID, or None if no
        association exists.
    """
    assoc_by_auth_id_model = (
        auth_models.UserIdentifiersModel.get_by_gae_id(auth_id))
    return (
        None if assoc_by_auth_id_model is None else
        assoc_by_auth_id_model.user_id)


def get_multi_user_ids_from_auth_ids(auth_ids):
    """Returns the user IDs associated with the given auth IDs.

    Args:
        auth_ids: list(str). The auth IDs.

    Returns:
        list(str|None). The user IDs associated with each of the given auth IDs,
        or None for associations which don't exist.
    """
    assoc_by_auth_id_models = auth_models.UserIdentifiersModel.get_multi(
        auth_ids, include_deleted=True)
    return [None if m is None else m.user_id for m in assoc_by_auth_id_models]


def associate_auth_id_with_user_id(auth_id_user_id_pair):
    """Commits the association between auth ID and user ID.

    Args:
        auth_id_user_id_pair: auth_domain.AuthIdUserIdPair. The association to
            commit.

    Raises:
        Exception. The IDs are already associated with a value.
    """
    auth_id, user_id = auth_id_user_id_pair

    user_id_collision = get_user_id_from_auth_id(auth_id)
    if user_id_collision is not None:
        raise Exception('auth_id=%r is already associated with user_id=%r' % (
            auth_id, user_id_collision))

    auth_id_collision = get_auth_id_from_user_id(user_id)
    if auth_id_collision is not None:
        raise Exception('user_id=%r is already associated with auth_id=%r' % (
            user_id, auth_id_collision))

    # A new {auth_id: user_id} mapping needs to be created. We know the model
    # doesn't exist because get_auth_id_from_user_id returned None.
    assoc_by_auth_id_model = (
        auth_models.UserIdentifiersModel(id=auth_id, user_id=user_id))
    assoc_by_auth_id_model.update_timestamps()
    assoc_by_auth_id_model.put()

    # The {user_id: auth_id} mapping needs to be created, but the model used to
    # store the relationship might already exist because other services use it
    # as well (e.g. user_services uses UserAuthDetailsModel.parent_user_id). In
    # such situations, the return value of get_auth_id_from_user_id would be
    # None, so that isn't strong enough to determine whether we need to create a
    # new model rather than update an existing one.
    assoc_by_user_id_model = (
        auth_models.UserAuthDetailsModel.get(user_id, strict=False))
    if assoc_by_user_id_model is None or assoc_by_user_id_model.gae_id is None:
        assoc_by_user_id_model = (
            auth_models.UserAuthDetailsModel(id=user_id, gae_id=auth_id))
        assoc_by_user_id_model.update_timestamps()
        assoc_by_user_id_model.put()


def associate_multi_auth_ids_with_user_ids(auth_id_user_id_pairs):
    """Commits the associations between auth IDs and user IDs.

    Args:
        auth_id_user_id_pairs: list(auth_domain.AuthIdUserIdPair). The
            associations to commit.

    Raises:
        Exception. One or more auth associations already exist.
    """
    # Turn list(pair) to pair(list): https://stackoverflow.com/a/7558990/4859885
    auth_ids, user_ids = python_utils.ZIP(*auth_id_user_id_pairs)

    user_id_collisions = get_multi_user_ids_from_auth_ids(auth_ids)
    if any(user_id is not None for user_id in user_id_collisions):
        user_id_collisions = ', '.join(
            '{auth_id=%r: user_id=%r}' % (auth_id, user_id)
            for auth_id, user_id in python_utils.ZIP(
                auth_ids, user_id_collisions)
            if user_id is not None)
        raise Exception('already associated: %s' % user_id_collisions)

    auth_id_collisions = get_multi_auth_ids_from_user_ids(user_ids)
    if any(auth_id is not None for auth_id in auth_id_collisions):
        auth_id_collisions = ', '.join(
            '{user_id=%r: auth_id=%r}' % (user_id, auth_id)
            for user_id, auth_id in python_utils.ZIP(
                user_ids, auth_id_collisions)
            if auth_id is not None)
        raise Exception('already associated: %s' % auth_id_collisions)

    # A new {auth_id: user_id} mapping needs to be created. We know the model
    # doesn't exist because get_auth_id_from_user_id returned None.
    assoc_by_auth_id_models = [
        auth_models.UserIdentifiersModel(id=auth_id, user_id=user_id)
        for auth_id, user_id in python_utils.ZIP(auth_ids, user_ids)
    ]
    auth_models.UserIdentifiersModel.update_timestamps_multi(
        assoc_by_auth_id_models)
    auth_models.UserIdentifiersModel.put_multi(assoc_by_auth_id_models)

    # The {user_id: auth_id} mapping needs to be created, but the model used to
    # store the relationship might already exist because other services use it
    # as well (e.g. user_services uses UserAuthDetailsModel.parent_user_id). In
    # such situations, the return value of get_multi_auth_ids_from_user_ids
    # would be None, so that isn't strong enough to determine whether we need to
    # create a new model rather than update an existing one.
    assoc_by_user_id_models = [
        auth_models.UserAuthDetailsModel(id=user_id, gae_id=auth_id)
        for auth_id, user_id, assoc_by_user_id_model in python_utils.ZIP(
            auth_ids, user_ids,
            auth_models.UserAuthDetailsModel.get_multi(user_ids))
        if (assoc_by_user_id_model is None or
            assoc_by_user_id_model.gae_id is None)
    ]
    if assoc_by_user_id_models:
        auth_models.UserAuthDetailsModel.update_timestamps_multi(
            assoc_by_user_id_models)
        auth_models.UserAuthDetailsModel.put_multi(assoc_by_user_id_models)
