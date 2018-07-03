# -*- coding: utf-8 -*-
"""Utils related to UPnP and DLNA."""

import logging
from xml.etree import ElementTree as ET

import voluptuous as vol

from async_upnp_client import UpnpError


_LOGGER = logging.getLogger(__name__)


def dlna_handle_notify_last_change(state_var):
    """
    Handle changes to LastChange state variable.

    This expands all changed state variables in the LastChange state variable.
    Note that the callback is called twice:
    - for the original event;
    - for the expanded event, via this function.
    """
    if state_var.name != 'LastChange':
        raise UpnpError('Call this only on state variable LastChange')

    service = state_var.service
    changed_state_variables = []

    el_event = ET.fromstring(state_var.value)
    _LOGGER.debug("Event payload: %s" % state_var.value)
    for el_instance in el_event:
        if not el_instance.tag.endswith("}InstanceID"):
            continue

        if el_instance.attrib['val'] != '0':
            _LOGGER.warning('Only InstanceID 0 is supported')
            continue

        for el_state_var in el_instance:
            name = el_state_var.tag.split('}')[1]
            state_var = service.state_variable(name)
            if state_var is None:
                _LOGGER.debug("State variable %s does not exist, ignoring", name)
                continue

            value = el_state_var.attrib['val']
            try:
                state_var.upnp_value = value
            except vol.error.MultipleInvalid:
                _LOGGER.error('Got invalid value for %s: %s', state_var, value)
            changed_state_variables.append(state_var)

    service.notify_changed_state_variables(changed_state_variables)
