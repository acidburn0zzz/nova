# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""Unit Tests for network code."""

from nova.network import linux_net
from nova import test


class IptablesManagerTestCase(test.TestCase):

    binary_name = linux_net.get_binary_name()

    sample_filter = ['#Generated by iptables-save on Fri Feb 18 15:17:05 2011',
                     '*filter',
                     ':INPUT ACCEPT [2223527:305688874]',
                     ':FORWARD ACCEPT [0:0]',
                     ':OUTPUT ACCEPT [2172501:140856656]',
                     ':iptables-top-rule - [0:0]',
                     ':iptables-bottom-rule - [0:0]',
                     ':%s-FORWARD - [0:0]' % (binary_name),
                     ':%s-INPUT - [0:0]' % (binary_name),
                     ':%s-local - [0:0]' % (binary_name),
                     ':%s-OUTPUT - [0:0]' % (binary_name),
                     ':nova-filter-top - [0:0]',
                     '[0:0] -A FORWARD -j nova-filter-top',
                     '[0:0] -A OUTPUT -j nova-filter-top',
                     '[0:0] -A nova-filter-top -j %s-local' % (binary_name),
                     '[0:0] -A INPUT -j %s-INPUT' % (binary_name),
                     '[0:0] -A OUTPUT -j %s-OUTPUT' % (binary_name),
                     '[0:0] -A FORWARD -j %s-FORWARD' % (binary_name),
                     '[0:0] -A INPUT -i virbr0 -p udp -m udp --dport 53 '
                     '-j ACCEPT',
                     '[0:0] -A INPUT -i virbr0 -p tcp -m tcp --dport 53 '
                     '-j ACCEPT',
                     '[0:0] -A INPUT -i virbr0 -p udp -m udp --dport 67 '
                     '-j ACCEPT',
                     '[0:0] -A INPUT -i virbr0 -p tcp -m tcp --dport 67 '
                     '-j ACCEPT',
                     '[0:0] -A FORWARD -s 192.168.122.0/24 -i virbr0 '
                     '-j ACCEPT',
                     '[0:0] -A FORWARD -i virbr0 -o virbr0 -j ACCEPT',
                     '[0:0] -A FORWARD -o virbr0 -j REJECT --reject-with '
                     'icmp-port-unreachable',
                     '[0:0] -A FORWARD -i virbr0 -j REJECT --reject-with '
                     'icmp-port-unreachable',
                     'COMMIT',
                     '# Completed on Fri Feb 18 15:17:05 2011']

    sample_nat = ['# Generated by iptables-save on Fri Feb 18 15:17:05 2011',
                  '*nat',
                  ':PREROUTING ACCEPT [3936:762355]',
                  ':INPUT ACCEPT [2447:225266]',
                  ':OUTPUT ACCEPT [63491:4191863]',
                  ':POSTROUTING ACCEPT [63112:4108641]',
                  ':%s-OUTPUT - [0:0]' % (binary_name),
                  ':%s-snat - [0:0]' % (binary_name),
                  ':%s-PREROUTING - [0:0]' % (binary_name),
                  ':%s-float-snat - [0:0]' % (binary_name),
                  ':%s-POSTROUTING - [0:0]' % (binary_name),
                  ':nova-postrouting-bottom - [0:0]',
                  '[0:0] -A PREROUTING -j %s-PREROUTING' % (binary_name),
                  '[0:0] -A OUTPUT -j %s-OUTPUT' % (binary_name),
                  '[0:0] -A POSTROUTING -j %s-POSTROUTING' % (binary_name),
                  '[0:0] -A nova-postrouting-bottom '
                  '-j %s-snat' % (binary_name),
                  '[0:0] -A %s-snat '
                  '-j %s-float-snat' % (binary_name, binary_name),
                  '[0:0] -A POSTROUTING -j nova-postrouting-bottom',
                  'COMMIT',
                  '# Completed on Fri Feb 18 15:17:05 2011']

    def setUp(self):
        super(IptablesManagerTestCase, self).setUp()
        self.manager = linux_net.IptablesManager()

    def test_duplicate_rules_no_dirty(self):
        table = self.manager.ipv4['filter']
        table.dirty = False
        num_rules = len(table.rules)
        table.add_rule('FORWARD', '-s 1.2.3.4/5 -j DROP')
        self.assertEqual(len(table.rules), num_rules + 1)
        self.assertTrue(table.dirty)
        table.dirty = False
        num_rules = len(table.rules)
        table.add_rule('FORWARD', '-s 1.2.3.4/5 -j DROP')
        self.assertEqual(len(table.rules), num_rules)
        self.assertFalse(table.dirty)

    def test_clean_tables_no_apply(self):
        for table in self.manager.ipv4.itervalues():
            table.dirty = False
        for table in self.manager.ipv6.itervalues():
            table.dirty = False

        def error_apply():
            raise test.TestingException()

        self.stubs.Set(self.manager, '_apply', error_apply)
        self.manager.apply()

    def test_filter_rules_are_wrapped(self):
        current_lines = self.sample_filter

        table = self.manager.ipv4['filter']
        table.add_rule('FORWARD', '-s 1.2.3.4/5 -j DROP')
        new_lines = self.manager._modify_rules(current_lines, table, 'filter')
        self.assertTrue('[0:0] -A %s-FORWARD '
                        '-s 1.2.3.4/5 -j DROP' % self.binary_name in new_lines)

        table.remove_rule('FORWARD', '-s 1.2.3.4/5 -j DROP')
        new_lines = self.manager._modify_rules(current_lines, table, 'filter')
        self.assertTrue('[0:0] -A %s-FORWARD '
                        '-s 1.2.3.4/5 -j DROP' % self.binary_name
                        not in new_lines)

    def test_remove_rules_regex(self):
        current_lines = self.sample_nat
        table = self.manager.ipv4['nat']
        table.add_rule('float-snat', '-s 10.0.0.1 -j SNAT --to 10.10.10.10'
                       ' -d 10.0.0.1')
        table.add_rule('float-snat', '-s 10.0.0.1 -j SNAT --to 10.10.10.10'
                       ' -o eth0')
        table.add_rule('PREROUTING', '-d 10.10.10.10 -j DNAT --to 10.0.0.1')
        table.add_rule('OUTPUT', '-d 10.10.10.10 -j DNAT --to 10.0.0.1')
        table.add_rule('float-snat', '-s 10.0.0.10 -j SNAT --to 10.10.10.11'
                       ' -d 10.0.0.10')
        table.add_rule('float-snat', '-s 10.0.0.10 -j SNAT --to 10.10.10.11'
                       ' -o eth0')
        table.add_rule('PREROUTING', '-d 10.10.10.11 -j DNAT --to 10.0.0.10')
        table.add_rule('OUTPUT', '-d 10.10.10.11 -j DNAT --to 10.0.0.10')
        new_lines = self.manager._modify_rules(current_lines, table, 'nat')
        self.assertEqual(len(new_lines) - len(current_lines), 8)
        regex = '.*\s+%s(/32|\s+|$)'
        num_removed = table.remove_rules_regex(regex % '10.10.10.10')
        self.assertEqual(num_removed, 4)
        new_lines = self.manager._modify_rules(current_lines, table, 'nat')
        self.assertEqual(len(new_lines) - len(current_lines), 4)
        num_removed = table.remove_rules_regex(regex % '10.10.10.11')
        self.assertEqual(num_removed, 4)
        new_lines = self.manager._modify_rules(current_lines, table, 'nat')
        self.assertEqual(new_lines, current_lines)

    def test_nat_rules(self):
        current_lines = self.sample_nat
        new_lines = self.manager._modify_rules(current_lines,
                                               self.manager.ipv4['nat'],
                                               'nat')

        for line in [':%s-OUTPUT - [0:0]' % (self.binary_name),
                     ':%s-float-snat - [0:0]' % (self.binary_name),
                     ':%s-snat - [0:0]' % (self.binary_name),
                     ':%s-PREROUTING - [0:0]' % (self.binary_name),
                     ':%s-POSTROUTING - [0:0]' % (self.binary_name)]:
            self.assertTrue(line in new_lines, "One of our chains went"
                                               " missing.")

        seen_lines = set()
        for line in new_lines:
            line = line.strip()
            self.assertTrue(line not in seen_lines,
                            "Duplicate line: %s" % line)
            seen_lines.add(line)

        last_postrouting_line = ''

        for line in new_lines:
            if line.startswith('[0:0] -A POSTROUTING'):
                last_postrouting_line = line

        self.assertTrue('-j nova-postrouting-bottom' in last_postrouting_line,
                        "Last POSTROUTING rule does not jump to "
                        "nova-postouting-bottom: %s" % last_postrouting_line)

        for chain in ['POSTROUTING', 'PREROUTING', 'OUTPUT']:
            self.assertTrue('[0:0] -A %s -j %s-%s' %
                            (chain, self.binary_name, chain) in new_lines,
                            "Built-in chain %s not wrapped" % (chain,))

    def test_filter_rules(self):
        current_lines = self.sample_filter
        new_lines = self.manager._modify_rules(current_lines,
                                               self.manager.ipv4['filter'],
                                               'nat')

        for line in [':%s-FORWARD - [0:0]' % (self.binary_name),
                     ':%s-INPUT - [0:0]' % (self.binary_name),
                     ':%s-local - [0:0]' % (self.binary_name),
                     ':%s-OUTPUT - [0:0]' % (self.binary_name)]:
            self.assertTrue(line in new_lines, "One of our chains went"
                                               " missing.")

        seen_lines = set()
        for line in new_lines:
            line = line.strip()
            self.assertTrue(line not in seen_lines,
                            "Duplicate line: %s" % line)
            seen_lines.add(line)

        for chain in ['FORWARD', 'OUTPUT']:
            for line in new_lines:
                if line.startswith('[0:0] -A %s' % chain):
                    self.assertTrue('-j nova-filter-top' in line,
                                    "First %s rule does not "
                                    "jump to nova-filter-top" % chain)
                    break

        self.assertTrue('[0:0] -A nova-filter-top '
                        '-j %s-local' % self.binary_name in new_lines,
                        "nova-filter-top does not jump to wrapped local chain")

        for chain in ['INPUT', 'OUTPUT', 'FORWARD']:
            self.assertTrue('[0:0] -A %s -j %s-%s' %
                            (chain, self.binary_name, chain) in new_lines,
                            "Built-in chain %s not wrapped" % (chain,))

    def test_missing_table(self):
        current_lines = []
        new_lines = self.manager._modify_rules(current_lines,
                                               self.manager.ipv4['filter'],
                                               'filter')

        for line in ['*filter',
                     'COMMIT']:
            self.assertTrue(line in new_lines, "One of iptables key lines"
                            "went missing.")

        self.assertTrue(len(new_lines) > 4, "No iptables rules added")

        self.assertTrue("#Generated by nova" == new_lines[0] and
                        "*filter" == new_lines[1] and
                        "COMMIT" == new_lines[-2] and
                        "#Completed by nova" == new_lines[-1],
                        "iptables rules not generated in the correct order")

    def test_iptables_top_order(self):
        # Test iptables_top_regex
        current_lines = list(self.sample_filter)
        current_lines[12:12] = ['[0:0] -A FORWARD -j iptables-top-rule']
        self.flags(iptables_top_regex='-j iptables-top-rule')
        new_lines = self.manager._modify_rules(current_lines,
                                               self.manager.ipv4['filter'],
                                               'filter')
        self.assertEqual(current_lines, new_lines)

    def test_iptables_bottom_order(self):
        # Test iptables_bottom_regex
        current_lines = list(self.sample_filter)
        current_lines[26:26] = ['[0:0] -A FORWARD -j iptables-bottom-rule']
        self.flags(iptables_bottom_regex='-j iptables-bottom-rule')
        new_lines = self.manager._modify_rules(current_lines,
                                               self.manager.ipv4['filter'],
                                               'filter')
        self.assertEqual(current_lines, new_lines)

    def test_iptables_preserve_order(self):
        # Test both iptables_top_regex and iptables_bottom_regex
        current_lines = list(self.sample_filter)
        current_lines[12:12] = ['[0:0] -A FORWARD -j iptables-top-rule']
        current_lines[27:27] = ['[0:0] -A FORWARD -j iptables-bottom-rule']
        self.flags(iptables_top_regex='-j iptables-top-rule')
        self.flags(iptables_bottom_regex='-j iptables-bottom-rule')
        new_lines = self.manager._modify_rules(current_lines,
                                               self.manager.ipv4['filter'],
                                               'filter')
        self.assertEqual(current_lines, new_lines)
