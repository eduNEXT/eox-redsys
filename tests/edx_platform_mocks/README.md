# Open edX test boundary

These Open edX API/model doubles are adapted from the AGPL v3 licensed
`zeit-labs/openedx-zeitlabs-payments` test fixtures at
`f1669db7020951f810b9d9a3b3b996cfaf12fd36`, directory
`test_utils/edx_platform_mocks`. The upstream GNU Affero General Public
License version 3, including Zeitlabs' additional clarification, is reproduced
unchanged in [LICENSE.txt](LICENSE.txt).
They represent only the external Open edX boundary. All shared Cart,
Transaction, Invoice and AuditLog models, migrations, processors, invoice
creation and course fulfillment logic run from the installed pinned package.
