# 1. System Architecture

## 1.1 Overview
The platform is composed of four independently deployable services: the
ingestion service, the retrieval service, the generation service, and the
admin gateway. Each service owns its own database and communicates with
the others only through the internal message bus.

## 1.2 Deployment Topology
Services are deployed as containers behind a load balancer. Each service
runs a minimum of two replicas in production. The admin gateway is the
only service exposed directly to the public internet; all other services
are reachable only from inside the private network.

## 1.3 Failure Domains
Each service is isolated in its own failure domain. If the generation
service becomes unavailable, ingestion and retrieval continue operating
normally and requests are queued rather than dropped.

# 2. Authentication

## 2.1 Password-Based Login
Users may authenticate with an email address and password. Passwords are
hashed using bcrypt with a work factor of 12 before storage. Plaintext
passwords are never logged or persisted.

## 2.2 Single Sign-On (SSO)
Enterprise customers may configure SAML 2.0 or OIDC-based single sign-on.
When SSO is enabled for an organization, password-based login is disabled
for all users in that organization unless an emergency-access account has
been explicitly configured by an administrator.

## 2.3 API Key Authentication
Programmatic access uses API keys instead of user sessions. API keys are
scoped to a single organization and can be restricted to read-only
access. API keys are shown in full only once, at creation time.

## 2.4 Session Expiry and Revocation
User sessions expire after 24 hours of inactivity. Administrators can
revoke all active sessions for a user immediately, for example after a
suspected credential compromise. Revocation takes effect within 60
seconds across all service replicas.

# 3. Authorization and Access Control

## 3.1 Role-Based Access Control
Every user is assigned one of three roles within an organization: viewer,
editor, or administrator. Viewers can read documents. Editors can read
and modify documents. Administrators can additionally manage users,
billing, and integration settings.

## 3.2 Resource-Level Permissions
In addition to organization-wide roles, individual documents and folders
can have permission overrides. A viewer can be granted editor access to a
single folder without changing their organization-wide role.

## 3.3 Audit Logging
Every permission change, login, and document access is written to an
append-only audit log. Audit log entries cannot be edited or deleted,
even by administrators, and are retained for a minimum of one year.

# 4. Data Ingestion Pipeline

## 4.1 Supported Source Types
The ingestion service accepts documents from direct upload, connected
cloud storage folders (Google Drive, SharePoint, Dropbox), and a public
REST API for programmatic ingestion.

## 4.2 File Validation
Uploaded files are checked against a maximum size limit of 200MB and a
list of allowed file types. Files that fail validation are rejected
before they enter the processing queue, and the uploader receives an
explanation of which check failed.

## 4.3 Duplicate Detection
Before processing, the ingestion service computes a content hash of each
file. If a file with an identical hash already exists in the
organization's workspace, the new upload is linked to the existing
document instead of being reprocessed.

# 5. Retrieval Pipeline

## 5.1 Chunking Strategy
Documents are split using recursive chunking: first by section heading,
then by paragraph if a section exceeds the maximum chunk size, then by
sentence as a last resort. This preserves logical boundaries wherever
possible instead of cutting at a fixed character count.

## 5.2 Embedding Generation
Each chunk is converted into a vector embedding using a sentence-level
embedding model. Embeddings are recomputed automatically whenever the
underlying document is edited.

## 5.3 Query-Time Retrieval
At query time, the user's question is embedded using the same model and
compared against stored chunk embeddings using cosine similarity. The
top-k most similar chunks are retrieved, where k defaults to 5 but can be
configured per integration.

## 5.4 Re-Ranking
Retrieved chunks are passed through a secondary re-ranking model that
scores relevance more precisely than raw cosine similarity. This step
exists because embedding similarity alone sometimes surfaces chunks that
are topically related but not actually responsive to the question.

# 6. Answer Generation

## 6.1 Context Construction
The top re-ranked chunks are assembled into a single context window,
along with their source metadata (document name, section, and page
number where available), before being sent to the language model.

## 6.2 Prompt Template
The generation service uses a fixed system prompt instructing the model
to answer only from the supplied context and to explicitly state when
the context does not contain a sufficient answer, rather than guessing.

## 6.3 Citation Attachment
Each generated answer is returned along with references to the specific
chunks used to produce it, allowing the end user to verify the answer
against the original source document.

# 7. Rate Limiting and Quotas

## 7.1 Request Rate Limits
API keys are limited to 60 requests per minute by default. Exceeding this
limit returns an HTTP 429 response with a Retry-After header indicating
how long to wait before retrying.

## 7.2 Monthly Query Quotas
Each pricing plan includes a monthly quota of retrieval queries. Usage
beyond the quota is either blocked or billed at an overage rate,
depending on the plan's configuration.

## 7.3 Burst Handling
Short bursts of traffic above the steady-state rate limit are permitted
using a token bucket algorithm, allowing brief spikes without immediately
rejecting requests.

# 8. Monitoring and Incident Response

## 8.1 Health Checks
Each service exposes a health check endpoint polled every 15 seconds by
the load balancer. A service that fails three consecutive health checks
is removed from rotation automatically.

## 8.2 Alerting Thresholds
Alerts are triggered when error rates exceed 1% over a five-minute
window, when p99 latency exceeds 2 seconds, or when queue depth exceeds
10,000 pending items.

## 8.3 Incident Severity Levels
Incidents are classified as SEV-1 (full outage), SEV-2 (significant
degradation), or SEV-3 (minor, non-customer-facing issue). SEV-1
incidents require a response within 15 minutes at any hour.
