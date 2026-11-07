# ConnectMQ for Home Assistant

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=connectmq&repository=connectmq-homeassistant&category=integration)

Connect Home Assistant to a [ConnectMQ](https://connectmq.com) managed MQTT broker in a minute, and keep an eye on your broker from Home Assistant.

ConnectMQ is a managed MQTT broker (MQTT 3.1.1 and 5.0, TLS with a publicly trusted certificate). The free Serverless plan supports up to 25 concurrent connections, QoS up to 1 and 256 KB messages, with no credit card needed. Create a broker at [app.connectmq.com](https://app.connectmq.com).

## What it does

- **Easy MQTT setup.** Sign in, pick a broker, and the integration fills in Home Assistant's own MQTT integration with the broker host, TLS port 8883, credentials and the client ID ConnectMQ expects. Nothing to copy by hand. If MQTT is already set up, your existing configuration is left untouched and the settings are shown in a notification instead.
- **Broker sensors.** One device per broker with:

| Entity | Description |
|---|---|
| Connected clients | MQTT clients connected to this broker right now |
| Account connections | Open connections across your account |
| Remaining connections | Connections left before the plan limit |
| Connection limit | The plan's concurrent connection limit (diagnostic) |
| Session minutes used | Session minutes used in the current period |
| Session minutes limit | The plan's session-minute limit (diagnostic) |
| Quota used | Share of the session-minute quota used, in % |
| Plan | The broker's plan (diagnostic) |
| Last client connected | When a client last connected |
| Broker active | Whether the broker is active |
| Broker node | Whether a dedicated broker node is online (only for brokers with their own node) |

This integration does not replace Home Assistant's MQTT integration; it configures it. Your MQTT devices, discovery and automations keep working through the standard MQTT integration.

## Installation

### Marketplace (recommended)

1. In Home Assistant, go to **Settings → Marketplace**, search for **ConnectMQ** and install it.  
   Until the listing is live, add it as a custom repository: **Settings → Marketplace → Add from link** and enter `connectmq/connectmq-homeassistant`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and choose **ConnectMQ**.

### Manual

Copy `custom_components/connectmq` into the `custom_components` folder of your Home Assistant configuration and restart.

## Configuration

1. Sign in with your ConnectMQ e-mail and password. If you signed up with Google or LinkedIn, set a password first with "Forgot password" in the portal.
2. Choose the broker (skipped when you have only one).
3. Leave **Set up the MQTT integration with this broker** on to connect Home Assistant's MQTT integration automatically.

Add the integration again to monitor more brokers.

### MQTT settings used

| Setting | Value |
|---|---|
| Broker | Your broker host, e.g. `broker.connectmq.com` |
| Port | `8883` (MQTT over TLS) |
| Protocol | MQTT 5 |
| Username / password | The broker's credentials from the ConnectMQ portal |
| Client ID | The issued client ID followed by `_homeassistant` |
| Broker certificate validation | Auto |

ConnectMQ only accepts the issued client ID or the issued ID followed by `_<suffix>`. If you configure MQTT by hand, set the client ID under *Advanced options*, otherwise the broker refuses the connection.

## How the sign-in is stored

The integration does not store your password. It keeps a ConnectMQ session (refresh token) that is renewed automatically. If the session expires, for example after Home Assistant has been offline for more than 30 days, Home Assistant asks you to sign in again. Removing the integration signs this session out.

## Troubleshooting

- **MQTT shows "Failed to connect"**: check that the client ID is the issued ID or `<issued ID>_<suffix>`, that the port is 8883 with certificate validation *Auto*, and that your plan has free connections (see the *Remaining connections* sensor).
- **Sign-in fails**: check your password at [app.connectmq.com](https://app.connectmq.com).
- Download diagnostics from the integration page when you open an issue; credentials and tokens are redacted.

## Links

- [ConnectMQ](https://connectmq.com) · [Portal](https://app.connectmq.com) · [Home Assistant MQTT guide](https://connectmq.com/blog/home-assistant-mqtt)
- [Issues](https://github.com/connectmq/connectmq-homeassistant/issues)

## License

MIT
