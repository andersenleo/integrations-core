# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os
import sys
from datetime import datetime

import mock
import pytest
from six import iteritems

from datadog_checks.base.utils.date import UTC, parse_rfc3339
from datadog_checks.kubelet import KubeletCheck, KubeletCredentials

# Skip the whole tests module on Windows
pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='tests for linux only')

# Constants
HERE = os.path.abspath(os.path.dirname(__file__))
QUANTITIES = {'12k': 12 * 1000, '12M': 12 * (1000 * 1000), '12Ki': 12.0 * 1024, '12K': 12.0, '12test': 12.0}

NODE_SPEC = {
    u'cloud_provider': u'GCE',
    u'instance_type': u'n1-standard-1',
    u'num_cores': 1,
    u'system_uuid': u'5556DC4F-C198-07C8-BE37-ACB98B1BA490',
    u'network_devices': [{u'mtu': 1460, u'speed': 0, u'name': u'eth0', u'mac_address': u'42:01:0a:84:00:04'}],
    u'hugepages': [{u'num_pages': 0, u'page_size': 2048}],
    u'memory_capacity': 3885424640,
    u'instance_id': u'8153046835786593062',
    u'boot_id': u'789bf9ff-77be-4f43-8352-62f84d5e4356',
    u'cpu_frequency_khz': 2600000,
    u'machine_id': u'5556dc4fc19807c8be37acb98b1ba490',
}

EXPECTED_METRICS_COMMON = [
    'kubernetes.pods.running',
    'kubernetes.containers.running',
    'kubernetes.containers.restarts',
    'kubernetes.cpu.capacity',
    'kubernetes.cpu.usage.total',
    'kubernetes.cpu.limits',
    'kubernetes.cpu.requests',
    'kubernetes.filesystem.usage',
    'kubernetes.filesystem.usage_pct',
    'kubernetes.memory.capacity',
    'kubernetes.memory.limits',
    'kubernetes.memory.requests',
    'kubernetes.memory.usage',
    'kubernetes.memory.working_set',
    'kubernetes.memory.cache',
    'kubernetes.memory.rss',
    'kubernetes.memory.swap',
    'kubernetes.network.rx_bytes',
    'kubernetes.network.tx_bytes',
]

EXPECTED_METRICS_PROMETHEUS = [
    'kubernetes.cpu.load.10s.avg',
    'kubernetes.cpu.system.total',
    'kubernetes.cpu.user.total',
    'kubernetes.cpu.cfs.throttled.periods',
    'kubernetes.cpu.cfs.throttled.seconds',
    'kubernetes.memory.usage_pct',
    'kubernetes.memory.sw_limit',
    'kubernetes.network.rx_dropped',
    'kubernetes.network.rx_errors',
    'kubernetes.network.tx_dropped',
    'kubernetes.network.tx_errors',
    'kubernetes.io.write_bytes',
    'kubernetes.io.read_bytes',
    'kubernetes.apiserver.certificate.expiration.count',
    'kubernetes.apiserver.certificate.expiration.sum',
    'kubernetes.rest.client.requests',
    'kubernetes.rest.client.latency.count',
    'kubernetes.rest.client.latency.sum',
    'kubernetes.kubelet.runtime.operations',
    'kubernetes.kubelet.runtime.errors',
    'kubernetes.kubelet.network_plugin.latency.sum',
    'kubernetes.kubelet.network_plugin.latency.count',
    'kubernetes.kubelet.network_plugin.latency.quantile',
    'kubernetes.kubelet.volume.stats.available_bytes',
    'kubernetes.kubelet.volume.stats.capacity_bytes',
    'kubernetes.kubelet.volume.stats.used_bytes',
    'kubernetes.kubelet.volume.stats.inodes',
    'kubernetes.kubelet.volume.stats.inodes_free',
    'kubernetes.kubelet.volume.stats.inodes_used',
]

COMMON_TAGS = {
    "kubernetes_pod://2edfd4d9-10ce-11e8-bd5a-42010af00137": ["pod_name:fluentd-gcp-v2.0.10-9q9t4"],
    "kubernetes_pod://2fdfd4d9-10ce-11e8-bd5a-42010af00137": ["pod_name:fluentd-gcp-v2.0.10-p13r3"],
    'docker://5741ed2471c0e458b6b95db40ba05d1a5ee168256638a0264f08703e48d76561': [
        'kube_container_name:fluentd-gcp',
        'kube_deployment:fluentd-gcp-v2.0.10',
    ],
    "docker://580cb469826a10317fd63cc780441920f49913ae63918d4c7b19a72347645b05": [
        'kube_container_name:prometheus-to-sd-exporter',
        'kube_deployment:fluentd-gcp-v2.0.10',
    ],
    'docker://6941ed2471c0e458b6b95db40ba05d1a5ee168256638a0264f08703e48d76561': [
        'kube_container_name:fluentd-gcp',
        'kube_deployment:fluentd-gcp-v2.0.10',
    ],
    "docker://690cb469826a10317fd63cc780441920f49913ae63918d4c7b19a72347645b05": [
        'kube_container_name:prometheus-to-sd-exporter',
        'kube_deployment:fluentd-gcp-v2.0.10',
    ],
    "docker://5f93d91c7aee0230f77fbe9ec642dd60958f5098e76de270a933285c24dfdc6f": [
        "pod_name:demo-app-success-c485bc67b-klj45"
    ],
    "kubernetes_pod://d2e71e36-10d0-11e8-bd5a-42010af00137": ['pod_name:dd-agent-q6hpw'],
    "kubernetes_pod://260c2b1d43b094af6d6b4ccba082c2db": ['pod_name:kube-proxy-gke-haissam-default-pool-be5066f1-wnvn'],
    "kubernetes_pod://24d6daa3-10d8-11e8-bd5a-42010af00137": ['pod_name:demo-app-success-c485bc67b-klj45'],
    "docker://f69aa93ce78ee11e78e7c75dc71f535567961740a308422dafebdb4030b04903": ['pod_name:pi-kff76'],
    "kubernetes_pod://12ceeaa9-33ca-11e6-ac8f-42010af00003": ['pod_name:dd-agent-ntepl'],
    "docker://32fc50ecfe24df055f6d56037acb966337eef7282ad5c203a1be58f2dd2fe743": ['pod_name:dd-agent-ntepl'],
}

METRICS_WITH_DEVICE_TAG = {
    'kubernetes.filesystem.usage': '/dev/sda1',
    'kubernetes.io.read_bytes': '/dev/sda',
    'kubernetes.io.write_bytes': '/dev/sda',
}

METRICS_WITH_INTERFACE_TAG = {
    'kubernetes.network.rx_bytes': 'eth0',
    'kubernetes.network.tx_bytes': 'eth0',
    'kubernetes.network.rx_errors': 'eth0',
    'kubernetes.network.tx_errors': 'eth0',
    'kubernetes.network.rx_dropped': 'eth0',
    'kubernetes.network.tx_dropped': 'eth0',
}


class MockStreamResponse:
    """
    Mocks raw contents of a stream request for the podlist get
    """

    def __init__(self, filename):
        self.filename = filename

    @property
    def raw(self):
        return open(os.path.join(HERE, 'fixtures', self.filename))

    def json(self):
        with open(os.path.join(HERE, 'fixtures', self.filename)) as f:
            return json.load(f)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def tagger():
    from datadog_checks.base.stubs import tagger

    tagger.reset()
    tagger.set_tags(COMMON_TAGS)
    return tagger


def mock_kubelet_check(monkeypatch, instances):
    """
    Returns a check that uses mocked data for responses from prometheus endpoints, pod list,
    and node spec.
    """
    check = KubeletCheck('kubelet', None, {}, instances)
    monkeypatch.setattr(check, 'retrieve_pod_list', mock.Mock(return_value=json.loads(mock_from_file('pods.json'))))
    monkeypatch.setattr(check, '_retrieve_node_spec', mock.Mock(return_value=NODE_SPEC))
    monkeypatch.setattr(check, '_perform_kubelet_check', mock.Mock(return_value=None))
    monkeypatch.setattr(check, '_compute_pod_expiration_datetime', mock.Mock(return_value=None))

    def mocked_poll(*args, **kwargs):
        scraper_config = args[0]
        prometheus_url = scraper_config['prometheus_url']

        attrs = None
        if prometheus_url.endswith('/metrics/cadvisor'):
            # Mock response for "/metrics/cadvisor"
            attrs = {
                'close.return_value': True,
                'iter_lines.return_value': mock_from_file('cadvisor_metrics.txt').split('\n'),
            }
        elif prometheus_url.endswith('/metrics'):
            # Mock response for "/metrics"
            attrs = {
                'close.return_value': True,
                'iter_lines.return_value': mock_from_file('kubelet_metrics.txt').split('\n'),
            }
        else:
            raise Exception("Must be a valid endpoint")

        return mock.Mock(headers={'Content-Type': 'text/plain'}, **attrs)

    monkeypatch.setattr(check, 'poll', mock.Mock(side_effect=mocked_poll))

    return check


def mock_from_file(fname):
    with open(os.path.join(HERE, 'fixtures', fname)) as f:
        return f.read()


def test_bad_config():
    with pytest.raises(Exception):
        KubeletCheck('kubelet', None, {}, [{}, {}])


def test_parse_quantity():
    for raw, res in iteritems(QUANTITIES):
        assert KubeletCheck.parse_quantity(raw) == res


def test_kubelet_default_options():
    check = KubeletCheck('kubelet', None, {}, [{}])
    assert check.cadvisor_scraper_config['namespace'] == 'kubernetes'
    assert check.kubelet_scraper_config['namespace'] == 'kubernetes'

    assert isinstance(check.cadvisor_scraper_config, dict)
    assert isinstance(check.kubelet_scraper_config, dict)


def test_kubelet_check_prometheus_instance_tags(monkeypatch, aggregator, tagger):
    _test_kubelet_check_prometheus(monkeypatch, aggregator, tagger, ["instance:tag"])


def test_kubelet_check_prometheus_no_instance_tags(monkeypatch, aggregator, tagger):
    _test_kubelet_check_prometheus(monkeypatch, aggregator, tagger, None)


def _test_kubelet_check_prometheus(monkeypatch, aggregator, tagger, instance_tags):
    instance = {}
    if instance_tags:
        instance["tags"] = instance_tags

    check = mock_kubelet_check(monkeypatch, [instance])
    monkeypatch.setattr(check, 'process_cadvisor', mock.Mock(return_value=None))

    check.check(instance)
    assert check.cadvisor_legacy_url is None
    check.retrieve_pod_list.assert_called_once()
    check._retrieve_node_spec.assert_called_once()
    check._perform_kubelet_check.assert_called_once()
    check.process_cadvisor.assert_not_called()

    # called twice so pct metrics are guaranteed to be there
    check.check(instance)
    for metric in EXPECTED_METRICS_COMMON:
        aggregator.assert_metric(metric)
        if instance_tags:
            for tag in instance_tags:
                aggregator.assert_metric_has_tag(metric, tag)
    for metric in EXPECTED_METRICS_PROMETHEUS:
        aggregator.assert_metric(metric)
        if instance_tags:
            for tag in instance_tags:
                aggregator.assert_metric_has_tag(metric, tag)

    assert aggregator.metrics_asserted_pct == 100.0


def test_prometheus_cpu_summed(monkeypatch, aggregator, tagger):
    check = mock_kubelet_check(monkeypatch, [{}])
    monkeypatch.setattr(check, 'rate', mock.Mock())
    check.check({"cadvisor_metrics_endpoint": "http://dummy/metrics/cadvisor", "kubelet_metrics_endpoint": ""})

    # Make sure we submit the summed rates correctly for containers:
    # - fluentd-gcp-v2.0.10-9q9t4 uses two cpus, we need to sum (1228.32 + 825.32) * 10**9 = 2053640000000
    # - demo-app-success-c485bc67b-klj45 is mono-threaded, we submit 7.756358313 * 10**9 = 7756358313
    #
    calls = [
        mock.call(
            'kubernetes.cpu.usage.total',
            2053640000000.0,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'],
        ),
        mock.call('kubernetes.cpu.usage.total', 7756358313.0, ['pod_name:demo-app-success-c485bc67b-klj45']),
    ]
    check.rate.assert_has_calls(calls, any_order=True)

    # Make sure the per-core metrics are not submitted
    bad_calls = [
        mock.call(
            'kubernetes.cpu.usage.total',
            1228320000000.0,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'],
        ),
        mock.call(
            'kubernetes.cpu.usage.total',
            825320000000.0,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'],
        ),
    ]
    for c in bad_calls:
        assert c not in check.rate.mock_calls


def test_prometheus_net_summed(monkeypatch, aggregator, tagger):
    check = mock_kubelet_check(monkeypatch, [{}])
    monkeypatch.setattr(check, 'rate', mock.Mock())
    check.check({"cadvisor_metrics_endpoint": "http://dummy/metrics/cadvisor", "kubelet_metrics_endpoint": ""})

    # Make sure we submit the summed rates correctly for pods:
    # - dd-agent-q6hpw has two interfaces, we need to sum (1.2638051777 + 2.2638051777) * 10**10 = 35276103554
    # - fluentd-gcp-v2.0.10-9q9t4 has one interface only, we submit 5.8107648 * 10**07 = 58107648
    #
    calls = [
        mock.call('kubernetes.network.rx_bytes', 35276103554.0, ['pod_name:dd-agent-q6hpw', 'interface:eth0']),
        mock.call('kubernetes.network.rx_bytes', 58107648.0, ['pod_name:fluentd-gcp-v2.0.10-9q9t4', 'interface:eth0']),
    ]
    check.rate.assert_has_calls(calls, any_order=True)

    bad_calls = [
        # Make sure the per-interface metrics are not submitted
        mock.call('kubernetes.network.rx_bytes', 12638051777.0, ['pod_name:dd-agent-q6hpw']),
        mock.call('kubernetes.network.rx_bytes', 22638051777.0, ['pod_name:dd-agent-q6hpw']),
        # Make sure hostNetwork pod metrics are not submitted, test with and without sum to be sure
        mock.call(
            'kubernetes.network.rx_bytes',
            (4917138204.0 + 698882782.0),
            ['pod_name:kube-proxy-gke-haissam-default-pool-be5066f1-wnvn'],
        ),
        mock.call(
            'kubernetes.network.rx_bytes', 4917138204.0, ['pod_name:kube-proxy-gke-haissam-default-pool-be5066f1-wnvn']
        ),
        mock.call(
            'kubernetes.network.rx_bytes', 698882782.0, ['pod_name:kube-proxy-gke-haissam-default-pool-be5066f1-wnvn']
        ),
    ]
    for c in bad_calls:
        assert c not in check.rate.mock_calls


def test_prometheus_filtering(monkeypatch, aggregator):
    # Let's intercept the container_cpu_usage_seconds_total
    # metric to make sure no sample with an empty pod_name
    # goes through input filtering
    # 12 out of the 45 samples should pass through the filter
    method_name = "datadog_checks.kubelet.prometheus.CadvisorPrometheusScraperMixin.container_cpu_usage_seconds_total"
    with mock.patch(method_name) as mock_method:
        check = mock_kubelet_check(monkeypatch, [{}])
        check.check({"cadvisor_metrics_endpoint": "http://dummy/metrics/cadvisor", "kubelet_metrics_endpoint": ""})

        mock_method.assert_called_once()
        metric = mock_method.call_args[0][0]
        assert len(metric.samples) == 12
        for name, labels, _ in metric.samples:
            assert name == "container_cpu_usage_seconds_total"
            assert labels["pod_name"] != ""


def test_kubelet_check_instance_config(monkeypatch):
    def mock_kubelet_check_no_prom():
        check = mock_kubelet_check(monkeypatch, [{}])

        monkeypatch.setattr(check, 'process', mock.Mock(return_value=None))
        monkeypatch.setattr(check, 'process_cadvisor', mock.Mock(return_value=None))

        return check

    check = mock_kubelet_check_no_prom()
    check.check({"cadvisor_port": 0, "cadvisor_metrics_endpoint": "", "kubelet_metrics_endpoint": ""})

    assert check.cadvisor_legacy_url is None
    check.retrieve_pod_list.assert_called_once()
    check._retrieve_node_spec.assert_called_once()
    check._perform_kubelet_check.assert_called_once()
    check.process_cadvisor.assert_not_called()

    check = mock_kubelet_check_no_prom()
    check.check({"cadvisor_port": 0, "metrics_endpoint": "", "kubelet_metrics_endpoint": "http://dummy"})


def test_report_pods_running(monkeypatch, tagger):
    check = KubeletCheck('kubelet', None, {}, [{}])
    monkeypatch.setattr(check, 'retrieve_pod_list', mock.Mock(return_value=json.loads(mock_from_file('pods.json'))))
    monkeypatch.setattr(check, 'gauge', mock.Mock())
    pod_list = check.retrieve_pod_list()

    check._report_pods_running(pod_list, [])

    calls = [
        mock.call('kubernetes.pods.running', 1, ["pod_name:fluentd-gcp-v2.0.10-9q9t4"]),
        mock.call('kubernetes.pods.running', 1, ["pod_name:fluentd-gcp-v2.0.10-p13r3"]),
        mock.call('kubernetes.pods.running', 1, ['pod_name:demo-app-success-c485bc67b-klj45']),
        mock.call(
            'kubernetes.containers.running',
            2,
            ["kube_container_name:fluentd-gcp", "kube_deployment:fluentd-gcp-v2.0.10"],
        ),
        mock.call(
            'kubernetes.containers.running',
            2,
            ["kube_container_name:prometheus-to-sd-exporter", "kube_deployment:fluentd-gcp-v2.0.10"],
        ),
        mock.call('kubernetes.containers.running', 1, ['pod_name:demo-app-success-c485bc67b-klj45']),
    ]
    check.gauge.assert_has_calls(calls, any_order=True)
    # Make sure non running container/pods are not sent
    bad_calls = [
        mock.call('kubernetes.pods.running', 1, ['pod_name:dd-agent-q6hpw']),
        mock.call('kubernetes.containers.running', 1, ['pod_name:dd-agent-q6hpw']),
    ]
    for c in bad_calls:
        assert c not in check.gauge.mock_calls


def test_report_pods_running_none_ids(monkeypatch, tagger):
    # Make sure the method is resilient to inconsistent podlists
    podlist = json.loads(mock_from_file('pods.json'))
    podlist["items"][0]['metadata']['uid'] = None
    podlist["items"][1]['status']['containerStatuses'][0]['containerID'] = None

    check = KubeletCheck('kubelet', None, {}, [{}])
    monkeypatch.setattr(check, 'retrieve_pod_list', mock.Mock(return_value=podlist))
    monkeypatch.setattr(check, 'gauge', mock.Mock())
    pod_list = check.retrieve_pod_list()

    check._report_pods_running(pod_list, [])

    calls = [
        mock.call('kubernetes.pods.running', 1, ["pod_name:fluentd-gcp-v2.0.10-9q9t4"]),
        mock.call(
            'kubernetes.containers.running',
            2,
            ["kube_container_name:prometheus-to-sd-exporter", "kube_deployment:fluentd-gcp-v2.0.10"],
        ),
    ]
    check.gauge.assert_has_calls(calls, any_order=True)


def test_report_container_spec_metrics(monkeypatch, tagger):
    check = KubeletCheck('kubelet', None, {}, [{}])
    monkeypatch.setattr(check, 'retrieve_pod_list', mock.Mock(return_value=json.loads(mock_from_file('pods.json'))))
    monkeypatch.setattr(check, 'gauge', mock.Mock())

    attrs = {'is_excluded.return_value': False}
    check.pod_list_utils = mock.Mock(**attrs)

    pod_list = check.retrieve_pod_list()
    instance_tags = ["one:1", "two:2"]
    check._report_container_spec_metrics(pod_list, instance_tags)

    calls = [
        mock.call(
            'kubernetes.cpu.requests',
            0.1,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'] + instance_tags,
        ),
        mock.call(
            'kubernetes.memory.requests',
            209715200.0,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'] + instance_tags,
        ),
        mock.call(
            'kubernetes.memory.limits',
            314572800.0,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'] + instance_tags,
        ),
        mock.call('kubernetes.cpu.requests', 0.1, instance_tags),
        mock.call('kubernetes.cpu.requests', 0.1, instance_tags),
        mock.call('kubernetes.memory.requests', 134217728.0, instance_tags),
        mock.call('kubernetes.cpu.limits', 0.25, instance_tags),
        mock.call('kubernetes.memory.limits', 536870912.0, instance_tags),
        mock.call('kubernetes.cpu.requests', 0.1, ["pod_name:demo-app-success-c485bc67b-klj45"] + instance_tags),
    ]
    if any(map(lambda e: 'pod_name:pi-kff76' in e, [x[0][2] for x in check.gauge.call_args_list])):
        raise AssertionError("kubernetes.cpu.requests was submitted for a non-running pod")
    check.gauge.assert_has_calls(calls, any_order=True)


def test_report_container_state_metrics(monkeypatch, tagger):
    check = KubeletCheck('kubelet', None, {}, [{}])
    check.pod_list_url = "dummyurl"
    monkeypatch.setattr(check, 'perform_kubelet_query', mock.Mock(return_value=MockStreamResponse('pods_crashed.json')))
    monkeypatch.setattr(check, '_compute_pod_expiration_datetime', mock.Mock(return_value=None))
    monkeypatch.setattr(check, 'gauge', mock.Mock())

    attrs = {'is_excluded.return_value': False}
    check.pod_list_utils = mock.Mock(**attrs)

    pod_list = check.retrieve_pod_list()

    instance_tags = ["one:1", "two:2"]
    check._report_container_state_metrics(pod_list, instance_tags)

    calls = [
        mock.call(
            'kubernetes.containers.last_state.terminated',
            1,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10']
            + instance_tags
            + ['reason:OOMKilled'],
        ),
        mock.call(
            'kubernetes.containers.state.waiting',
            1,
            ['kube_container_name:prometheus-to-sd-exporter', 'kube_deployment:fluentd-gcp-v2.0.10']
            + instance_tags
            + ['reason:CrashLoopBackOff'],
        ),
        mock.call(
            'kubernetes.containers.restarts',
            1,
            ['kube_container_name:fluentd-gcp', 'kube_deployment:fluentd-gcp-v2.0.10'] + instance_tags,
        ),
        mock.call(
            'kubernetes.containers.restarts',
            0,
            ['kube_container_name:prometheus-to-sd-exporter', 'kube_deployment:fluentd-gcp-v2.0.10'] + instance_tags,
        ),
    ]
    check.gauge.assert_has_calls(calls, any_order=True)

    container_state_gauges = [
        x[0][2] for x in check.gauge.call_args_list if x[0][0].startswith('kubernetes.containers.state')
    ]
    if any(map(lambda e: 'reason:TransientReason' in e, container_state_gauges)):
        raise AssertionError('kubernetes.containers.state.* was submitted with a transient reason')
    if any(map(lambda e: not any(x for x in e if x.startswith('reason:')), container_state_gauges)):
        raise AssertionError('kubernetes.containers.state.* was submitted without a reason')


def test_pod_expiration(monkeypatch, aggregator, tagger):
    check = KubeletCheck('kubelet', None, {}, [{}])
    check.pod_list_url = "dummyurl"

    # Fixtures contains four pods:
    #   - dd-agent-ntepl old but running
    #   - hello1-1550504220-ljnzx succeeded and old enough to expire
    #   - hello5-1550509440-rlgvf succeeded but not old enough
    #   - hello8-1550505780-kdnjx has one old container and a recent container, don't expire
    monkeypatch.setattr(check, 'perform_kubelet_query', mock.Mock(return_value=MockStreamResponse('pods_expired.json')))
    monkeypatch.setattr(
        check, '_compute_pod_expiration_datetime', mock.Mock(return_value=parse_rfc3339("2019-02-18T16:00:06Z"))
    )

    attrs = {'is_excluded.return_value': False}
    check.pod_list_utils = mock.Mock(**attrs)

    pod_list = check.retrieve_pod_list()
    assert pod_list['expired_count'] == 1

    expected_names = ['dd-agent-ntepl', 'hello5-1550509440-rlgvf', 'hello8-1550505780-kdnjx']
    collected_names = [p['metadata']['name'] for p in pod_list['items']]
    assert collected_names == expected_names

    # Test .pods.expired gauge is submitted
    check._report_container_state_metrics(pod_list, ["custom:tag"])
    aggregator.assert_metric("kubernetes.pods.expired", value=1, tags=["custom:tag"])

    # Ensure we can iterate twice over the podlist
    check._report_pods_running(pod_list, [])
    aggregator.assert_metric("kubernetes.pods.running", value=1, tags=["pod_name:dd-agent-ntepl"])
    aggregator.assert_metric("kubernetes.containers.running", value=1, tags=["pod_name:dd-agent-ntepl"])


class MockResponse(mock.Mock):
    @staticmethod
    def iter_lines():
        return []


def test_perform_kubelet_check(monkeypatch):
    check = KubeletCheck('kubelet', None, {}, [{}])
    check.kube_health_url = "http://127.0.0.1:10255/healthz"
    check.kubelet_credentials = KubeletCredentials({})
    monkeypatch.setattr(check, 'service_check', mock.Mock())

    instance_tags = ["one:1"]
    get = MockResponse()
    with mock.patch("requests.get", side_effect=get):
        check._perform_kubelet_check(instance_tags)

    get.assert_has_calls(
        [
            mock.call(
                'http://127.0.0.1:10255/healthz',
                cert=None,
                headers=None,
                params={'verbose': True},
                stream=False,
                timeout=10,
                verify=None,
            )
        ]
    )
    calls = [mock.call('kubernetes.kubelet.check', 0, tags=instance_tags)]
    check.service_check.assert_has_calls(calls)


def test_report_node_metrics(monkeypatch):
    check = KubeletCheck('kubelet', None, {}, [{}])
    monkeypatch.setattr(check, '_retrieve_node_spec', mock.Mock(return_value={'num_cores': 4, 'memory_capacity': 512}))
    monkeypatch.setattr(check, 'gauge', mock.Mock())
    check._report_node_metrics(['foo:bar'])
    calls = [
        mock.call('kubernetes.cpu.capacity', 4.0, ['foo:bar']),
        mock.call('kubernetes.memory.capacity', 512.0, ['foo:bar']),
    ]
    check.gauge.assert_has_calls(calls, any_order=False)


def test_retrieve_pod_list_success(monkeypatch):
    check = KubeletCheck('kubelet', None, {}, [{}])
    check.pod_list_url = "dummyurl"
    monkeypatch.setattr(check, 'perform_kubelet_query', mock.Mock(return_value=MockStreamResponse('pod_list_raw.dat')))
    monkeypatch.setattr(check, '_compute_pod_expiration_datetime', mock.Mock(return_value=None))

    retrieved = check.retrieve_pod_list()
    expected = json.loads(mock_from_file("pod_list_raw.json"))
    assert json.dumps(retrieved, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_retrieved_pod_list_failure(monkeypatch):
    def mock_perform_kubelet_query(s, stream=False):
        raise Exception("network error")

    check = KubeletCheck('kubelet', None, {}, [{}])
    check.pod_list_url = "dummyurl"
    monkeypatch.setattr(check, 'perform_kubelet_query', mock_perform_kubelet_query)

    retrieved = check.retrieve_pod_list()
    assert retrieved is None


def test_compute_pod_expiration_datetime(monkeypatch):
    # Invalid input
    with mock.patch("datadog_checks.kubelet.kubelet.get_config", return_value="") as p:
        assert KubeletCheck._compute_pod_expiration_datetime() is None
        p.assert_called_with("kubernetes_pod_expiration_duration")

    with mock.patch("datadog_checks.kubelet.kubelet.get_config", return_value="invalid"):
        assert KubeletCheck._compute_pod_expiration_datetime() is None

    # Disabled
    with mock.patch("datadog_checks.kubelet.kubelet.get_config", return_value="0"):
        assert KubeletCheck._compute_pod_expiration_datetime() is None

    # Set to 15 minutes
    with mock.patch("datadog_checks.kubelet.kubelet.get_config", return_value="900"):
        expire = KubeletCheck._compute_pod_expiration_datetime()
        assert expire is not None
        now = datetime.utcnow().replace(tzinfo=UTC)
        assert abs((now - expire).seconds - 60 * 15) < 2


def test_add_labels_to_tags(monkeypatch, aggregator):
    check = mock_kubelet_check(monkeypatch, [{}])
    check.check({"cadvisor_metrics_endpoint": "http://dummy/metrics/cadvisor", "kubelet_metrics_endpoint": ""})

    for metric in METRICS_WITH_DEVICE_TAG:
        tag = 'device:%s' % METRICS_WITH_DEVICE_TAG[metric]
        aggregator.assert_metric_has_tag(metric, tag)

    for metric in METRICS_WITH_INTERFACE_TAG:
        tag = 'interface:%s' % METRICS_WITH_INTERFACE_TAG[metric]
        aggregator.assert_metric_has_tag(metric, tag)
