# Agent Check: {integration_name}

## Overview

This check monitors [{integration_name}][1].

## Setup

### Installation

{install_info}

### Configuration

1. Edit the `{check_name}.d/conf.yaml` file, in the `conf.d/` folder at the root of your
   Agent's configuration directory to start collecting your {check_name} performance data.
   See the [sample {check_name}.d/conf.yaml][2] for all available configuration options.

   This check has a limit of 350 metrics per instance. The number of returned metrics is indicated in the info page.
   You can specify the metrics you are interested in by editing the configuration below.
   To learn how to customize the metrics to collect visit the [JMX Checks documentation][3] for more detailed instructions.
   If you need to monitor more metrics, contact [Datadog support][6].

2. [Restart the Agent][4]

### Validation

[Run the Agent's `status` subcommand][5] and look for `{check_name}` under the Checks section.

## Data Collected

### Metrics

{integration_name} does not include any metrics.

### Service Checks

{integration_name} does not include any service checks.

### Events

{integration_name} does not include any events.

## Troubleshooting

Need help? Contact [Datadog support][6].


[1]: **LINK_TO_INTEGERATION_SITE**
[2]: https://github.com/DataDog/integrations-core/blob/master/{check_name}/datadog_checks/{check_name}/data/conf.yaml.example
[3]: https://docs.datadoghq.com/integrations/java
[4]: https://docs.datadoghq.com/agent/guide/agent-commands/?tab=agentv6#start-stop-and-restart-the-agent
[5]: https://docs.datadoghq.com/agent/guide/agent-commands/?tab=agentv6#agent-status-and-information
[6]: https://docs.datadoghq.com/help
