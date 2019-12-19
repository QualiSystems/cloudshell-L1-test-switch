#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import time
from random import randint

import yaml
from lockfile import LockFile

from cloudshell.layer_one.core.driver_commands_interface import DriverCommandsInterface
from cloudshell.layer_one.core.response.resource_info.entities.port import Port
from cloudshell.layer_one.core.response.response_info import GetStateIdResponseInfo, AttributeValueResponseInfo
from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
from cloudshell.layer_one.core.response.response_info import ResourceDescriptionResponseInfo


# from entities import TestPort


class DriverCommands(DriverCommandsInterface):
    """
    Driver commands implementation
    """
    MAPPINGS_FILE_TEMPLATE = '{}-mappings.yaml'
    EXCEPTION = 'except'

    class MappingTransManager(object):

        def __init__(self, mappings_file):
            self._mappings_file = mappings_file
            self._lock_file = LockFile(self._mappings_file)
            self._mappings = None

        def __enter__(self):
            try:
                self._lock_file.acquire()
                with open(self._mappings_file, "r") as fd:
                    self._mappings = yaml.load(fd.read(), Loader=yaml.Loader)
            finally:
                self._mappings = self._mappings or {}
                return self._mappings

        def __exit__(self, exc_type, exc_val, exc_tb):
            data = yaml.dump(self._mappings, default_flow_style=False, allow_unicode=True, encoding=None)
            with(open(self._mappings_file, "w")) as fd:
                fd.write(data)
            self._lock_file.release()

    def __init__(self, logger, runtime_config):
        """
        :type logger: logging.Logger
        :type runtime_config: cloudshell.layer_one.core.helper.runtime_configuration.RuntimeConfiguration
        """
        self._logger = logger
        # self._runtime_config = runtime_config
        self._mapping_file = None
        self._delay_min = runtime_config.read_key("DELAY_MIN", 0)
        self._delay_max = runtime_config.read_key("DELAY_MAX", 0)
        self._override_mapping = runtime_config.read_key("OVERRIDE_MAPPING", True)

    def login(self, address, username, password):
        """
        Perform login operation on the device
        :param address: resource address, "192.168.42.240"
        :param username: username to login on the device
        :param password: password
        :return: None
        :raises Exception: if command failed
        Example:
            # Define session attributes
            self._cli_handler.define_session_attributes(address, username, password)

            # Obtain cli session
            with self._cli_handler.default_mode_service() as session:
                # Executing simple command
                device_info = session.send_command('show version')
                self._logger.info(device_info)
        """
        self._mapping_file = os.path.join(os.path.dirname(__file__), '..',
                                          self.MAPPINGS_FILE_TEMPLATE.format(address.replace('.', '-')))

    def get_state_id(self):
        """
        Check if CS synchronized with the device.
        :return: Synchronization ID, GetStateIdResponseInfo(-1) if not used
        :rtype: cloudshell.layer_one.core.response.response_info.GetStateIdResponseInfo
        :raises Exception: if command failed

        Example:
            # Obtain cli session
            with self._cli_handler.default_mode_service() as session:
                # Execute command
                chassis_name = session.send_command('show chassis name')
                return chassis_name
        """
        return GetStateIdResponseInfo(-1)

    def set_state_id(self, state_id):
        """
        Set synchronization state id to the device, called after Autoload or SyncFomDevice commands
        :param state_id: synchronization ID
        :type state_id: str
        :return: None
        :raises Exception: if command failed

        Example:
            # Obtain cli session
            with self._cli_handler.config_mode_service() as session:
                # Execute command
                session.send_command('set chassis name {}'.format(state_id))
        """
        pass

    def map_bidi(self, src_port, dst_port):
        """
        Create a bidirectional connection between source and destination ports
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_port: dst port address, '192.168.42.240/1/22'
        :type dst_port: str
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                session.send_command('map bidir {0} {1}'.format(convert_port(src_port), convert_port(dst_port)))

        """
        self._delay()
        with self.MappingTransManager(self._mapping_file) as mappings:
            self._check_exception(src_port, mappings)
            self._check_exception(dst_port, mappings)
            self._check_mapping_exist(src_port, dst_port, mappings)
            self._check_mapping_exist(dst_port, src_port, mappings)
            mappings[src_port] = dst_port
            mappings[dst_port] = src_port

    def map_uni(self, src_port, dst_ports):
        """
        Unidirectional mapping of two ports
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: list of dst ports addresses, ['192.168.42.240/1/22', '192.168.42.240/1/23']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                for dst_port in dst_ports:
                    session.send_command('map {0} also-to {1}'.format(convert_port(src_port), convert_port(dst_port)))
        """
        self._delay()
        with self.MappingTransManager(self._mapping_file) as mappings:
            self._check_exception(src_port, mappings)
            for dst_port in dst_ports:
                self._check_exception(dst_port, mappings)
                self._check_mapping_exist(src_port, dst_port, mappings)
                mappings[dst_port] = src_port

    def get_resource_description(self, address):
        """
        Auto-load function to retrieve all information from the device
        :param address: resource address, '192.168.42.240'
        :type address: str
        :return: resource description
        :rtype: cloudshell.layer_one.core.response.response_info.ResourceDescriptionResponseInfo
        :raises cloudshell.layer_one.core.layer_one_driver_exception.LayerOneDriverException: Layer one exception.

        Example:

        from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
        from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
        from cloudshell.layer_one.core.response.resource_info.entities.port import Port
        from cloudshell.layer_one.core.response.response_info import ResourceDescriptionResponseInfo

        chassis_resource_id = 1
        chassis_model_name = "Test Switch Chassis"
        chassis_serial_number = 'NA'
        chassis = Chassis(chassis_resource_id, address, chassis_model_name, chassis_serial_number)

        blade1 = Blade('1')
        blade1.set_parent_resource(chassis)
        blade2 = Blade('2')
        blade2.set_parent_resource(chassis)

        for port_id in range(1, 11):
            port = Port(port_id)
            port.set_parent_resource(blade1)

        for port_id in range(1, 11):
            port = Port(port_id)
            port.set_parent_resource(blade2)

        return ResourceDescriptionResponseInfo([chassis])
        """

        chassis_resource_id = 1
        chassis_model_name = "Test Switch Chassis"
        chassis_serial_number = 'NA'
        chassis = Chassis(chassis_resource_id, address, chassis_model_name, chassis_serial_number)

        blade1 = Blade('1')
        blade1.set_parent_resource(chassis)
        blade2 = Blade('2')
        blade2.set_parent_resource(chassis)
        ports = {}

        for port_id in range(1, 11):
            port = Port(port_id)
            # port.set_protocol('69')
            # port.set_protocol_type('2')
            # port.set_speed('5')
            port.set_parent_resource(blade1)
            ports[port.address] = port

        for port_id in range(1, 11):
            port = Port(port_id)
            # port.set_protocol('30')
            # port.set_protocol_type('2')
            # port.set_speed('4')
            port.set_parent_resource(blade2)
            ports[port.address] = port

        with self.MappingTransManager(self._mapping_file) as mappings:
            for dst_addr, src_addr in mappings.items():
                src_port = ports.get(src_addr)
                dst_port = ports.get(dst_addr)
                if src_port and dst_port:
                    dst_port.add_mapping(src_port)
                # mapped_to = self.mappings.get(addr)
                # if mapped_to:
                #     port.add_mapping(mapped_to)

        return ResourceDescriptionResponseInfo([chassis])

    def map_clear(self, ports):
        """
        Remove simplex/multi-cast/duplex connection ending on the destination port
        :param ports: ports, ['192.168.42.240/1/21', '192.168.42.240/1/22']
        :type ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            exceptions = []
            with self._cli_handler.config_mode_service() as session:
                for port in ports:
                    try:
                        session.send_command('map clear {}'.format(convert_port(port)))
                    except Exception as e:
                        exceptions.append(str(e))
                if exceptions:
                    raise Exception('self.__class__.__name__', ','.join(exceptions))
        """
        self._delay()
        with self.MappingTransManager(self._mapping_file) as mappings:
            act_ports = []
            for port in ports:
                act_ports.extend([k for k, v in mappings.items() if v == port or k == port])
            self._del_mappings(act_ports, mappings)

    def map_clear_to(self, src_port, dst_ports):
        """
        Remove simplex/multi-cast/duplex connection ending on the destination port
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: list of dst ports addresses, ['192.168.42.240/1/21', '192.168.42.240/1/22']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                _src_port = convert_port(src_port)
                for port in dst_ports:
                    _dst_port = convert_port(port)
                    session.send_command('map clear-to {0} {1}'.format(_src_port, _dst_port))
        """
        self._delay()
        with self.MappingTransManager(self._mapping_file) as mappings:
            act_ports = []
            self._check_exception(src_port, mappings)
            for dst_port in dst_ports:
                act_src = mappings.get(dst_port)
                if act_src == src_port:
                    act_ports.append(dst_port)

            self._del_mappings(act_ports, mappings)

    def _check_exception(self, port, mappings):
        data = mappings.get(port)
        if data and self.EXCEPTION in data.lower():
            raise Exception(data)

    def _del_mappings(self, ports, mappings):
        for port in ports:
            self._check_exception(port, mappings)
            mappings.pop(port, None)

    def _delay(self):
        delay = randint(int(self._delay_min), int(self._delay_max))
        self._logger.debug("Delay: {}".format(delay))
        time.sleep(delay)

    def _check_mapping_exist(self, src, dst, mappings):
        if not self._override_mapping:
            act_src = mappings.get(dst)
            if act_src and act_src != src:
                raise Exception(
                    "DST port already used in {}->{}, override mapping is not allowed.".format(act_src, dst))

    def get_attribute_value(self, cs_address, attribute_name):
        """
        Retrieve attribute value from the device
        :param cs_address: address, '192.168.42.240/1/21'
        :type cs_address: str
        :param attribute_name: attribute name, "Port Speed"
        :type attribute_name: str
        :return: attribute value
        :rtype: cloudshell.layer_one.core.response.response_info.AttributeValueResponseInfo
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                command = AttributeCommandFactory.get_attribute_command(cs_address, attribute_name)
                value = session.send_command(command)
                return AttributeValueResponseInfo(value)
        """
        pass

    def set_attribute_value(self, cs_address, attribute_name, attribute_value):
        """
        Set attribute value to the device
        :param cs_address: address, '192.168.42.240/1/21'
        :type cs_address: str
        :param attribute_name: attribute name, "Port Speed"
        :type attribute_name: str
        :param attribute_value: value, "10000"
        :type attribute_value: str
        :return: attribute value
        :rtype: cloudshell.layer_one.core.response.response_info.AttributeValueResponseInfo
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                command = AttributeCommandFactory.set_attribute_command(cs_address, attribute_name, attribute_value)
                session.send_command(command)
                return AttributeValueResponseInfo(attribute_value)
        """
        return AttributeValueResponseInfo(attribute_value)

    def map_tap(self, src_port, dst_ports):
        """
        Add TAP connection
        :param src_port: port to monitor '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: ['192.168.42.240/1/22', '192.168.42.240/1/23']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            return self.map_uni(src_port, dst_ports)
        """
        return self.map_uni(src_port, dst_ports)

    def set_speed_manual(self, src_port, dst_port, speed, duplex):
        """
        Set connection speed. It is not used with new standard
        :param src_port:
        :param dst_port:
        :param speed:
        :param duplex:
        :return:
        """
        raise NotImplementedError
