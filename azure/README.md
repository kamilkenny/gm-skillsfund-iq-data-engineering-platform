# Azure deployment notes

Existing Function App: `GMSkillsFundIQ` in resource group `GMSkillsFundIQ_group`, Germany West Central, Python 3.12, Flex Consumption, user-assigned managed identity.

No function has been deployed yet. Deployment must follow schema/data testing and Azure SQL subscription-cost confirmation.

Never commit connection strings, access keys or personal data. Prefer Microsoft Entra managed identity for Blob and Azure SQL, with least-privilege assignments verified after provisioning.

Cloud Shell currently has an ephemeral home directory. Authenticate `gh` every new session as needed and push verified changes immediately.
