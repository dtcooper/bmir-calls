# BMIR Call Routing Software

Here's the [Django](https://www.djangoproject.com/) app that routes calls to and
from [Burning Man Information Radio (BMIR)](https://bmir.org).

## Setup

Make sure you have a domain name point to the IP address of your machine. Set
`.env` file's `DOMAIN_NAME` value to the domain.

### Twilio Setup

#### Credential Lists

Create a Twilio credential list with usernames:

1. `broadcast` &mdash; The "broadcast desk" phone (or the `.env` value of
   `TWILIO_SIP_BROADCAST_USER`)
2. `outgoing` &mdash; An additional "outgoing" phone for calls (or the `.env`
    value of `TWILIO_SIP_OUTGOING_USER`)

#### SIP Domain

Create a Twilio SIP domain and set .env value
`TWILIO_SIP_DOMAIN="<name>.sip.twilio.com"`

On your SIP Domain, configure as follows

* Under **Voice Authentication**,
  * `Credential lists` &mdash; add the credential list as above.
* Under **Call Control Configuration**,
  * `A call comes in` &mdash; Set a Webhook to
    `https://<DOMAIN_NAME>/twilio/outgoing/` (HTTP POST)
  * `Call status changes` &mdash; Set to
    `<DOMAIN_NAME>/twilio/outgoing/status/` (HTTP POST)
* **Secure Media** set to disabled.
* Under **SIP Registration**,
  * `Endpoints CAN register with this Domain` &mdash; Set to enabled
  * `Credential lists` &mdash; add the credential list as above.

#### Phone Numbers

Create two phone numbers,

1. Your "broadcast desk" number (`.env` value `TWILIO_BROADCAST_NUMBER`)
2. Your (optional) "outgoing" number (`.env` value `TWILIO_OUTGOING_NUMBER`)
   * To disable this feature, leave it blank, or set it to the "broadcast desk"
     number,

##### "Broadcast Desk" Number

Configure your Twilio "broadcast desk" number as follows,

* Under **Voice Configuration**,
  * `A call comes in` &mdash; Set a Webhook to
    `https://<DOMAIN_NAME>/twilio/incoming/` (HTTP POST)


##### "Outgoing" Number (optional)

Optionally, configure your Twilio "outgoing" number as follows,

* Under **Voice Configuration**,
  * `A call comes in` &mdash; Set a Webhook to
    `https://<DOMAIN_NAME>/twilio/incoming/call-outgoing/` (HTTP POST)

**NOTE:** If you don't configure this, the outgoing phone will not be able to
receive calls.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
