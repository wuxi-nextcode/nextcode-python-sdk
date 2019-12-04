Server API Documention
======================

Serverside services are exposed via REST and documented in OpenAPI Spec. You can view the specification for each service here.

Authentication
----------------
All services use JWT authentication through a shared Keycloak server. All requests require a ``Bearer`` Authorization header with a temporary access token retrieved from the authentication server.

Typically the client will perform a username/password authentication once and store a *refresh token* locally. This is called an *API Key* in the SDK. For each request to a service the Bearer token will **not** be this refresh token but a temporary *access token* retrieved from the authentication server. This access token typically lasts for 10 minutes.

Gor Query API
-----------------
https://redocly.github.io/redoc/?url=https://wuxi-nextcode.github.io/nextcode-python-sdk/openapi/gor-query-api.json

Workflow Service
-----------------
https://redocly.github.io/redoc/?url=https://wuxi-nextcode.github.io/nextcode-python-sdk/openapi/workflow-service.json

Pipelines Service
-----------------
https://redocly.github.io/redoc/?url=https://wuxi-nextcode.github.io/nextcode-python-sdk/openapi/pipelines-service.json
