# Gitea API Reference

## Base URL

```
https://gitea.btcmap.org/api/v1
```

## Authentication

All API requests require authentication using a personal access token.

**Header**:
```
Authorization: token YOUR_TOKEN_HERE
```

**Getting a Token**:
1. Login to https://gitea.btcmap.org
2. Go to Settings → Applications
3. Generate New Token
4. Save the token securely

## Endpoints

### List Issues

```http
GET /repos/{owner}/{repo}/issues
```

**Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| state | string | Filter by state: `open`, `closed`, `all` |
| labels | string | Comma-separated list of labels |
| page | integer | Page number |
| limit | integer | Items per page (max 50) |

**Example**:
```bash
curl -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues?state=open&labels=type/location-submission&limit=10"
```

**Response**:
```json
[
  {
    "id": 12350,
    "number": 12079,
    "title": "Coldwater Mountain Brewpub",
    "body": "...",
    "state": "open",
    "labels": [
      {
        "id": 1307,
        "name": "import/square",
        "color": "0052cc"
      }
    ],
    "user": {
      "id": 4,
      "login": "btcmap-bot"
    },
    "assignee": null,
    "created_at": "2026-02-07T09:45:22Z",
    "updated_at": "2026-02-07T09:45:22Z",
    "comments": 0
  }
]
```

### Get Single Issue

```http
GET /repos/{owner}/{repo}/issues/{index}
```

**Example**:
```bash
curl -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/12079"
```

### Create Comment

```http
POST /repos/{owner}/{repo}/issues/{index}/comments
```

**Request Body**:
```json
{
  "body": "Comment text in **markdown**"
}
```

**Example**:
```bash
curl -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "Verification complete. Score: 90%"}' \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/12079/comments"
```

**Response**:
```json
{
  "id": 12345,
  "body": "Verification complete. Score: 90%",
  "user": {
    "id": 123,
    "login": "your-username"
  },
  "created_at": "2026-02-07T10:00:00Z"
}
```

### Edit Comment

```http
PATCH /repos/{owner}/{repo}/issues/comments/{id}
```

**Example**:
```bash
curl -X PATCH \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "Updated comment"}' \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/comments/12345"
```

### Add Labels

```http
POST /repos/{owner}/{repo}/issues/{index}/labels
```

**Request Body**:
```json
{
  "labels": ["status/pending"]
}
```

**Example**:
```bash
curl -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"labels": ["status/pending"]}' \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/12079/labels"
```

### Remove Label

```http
DELETE /repos/{owner}/{repo}/issues/{index}/labels/{label}
```

**Example**:
```bash
curl -X DELETE \
  -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/12079/labels/status/pending"
```

### Close Issue

```http
PATCH /repos/{owner}/{repo}/issues/{index}
```

**Request Body**:
```json
{
  "state": "closed"
}
```

**Example**:
```bash
curl -X PATCH \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"state": "closed"}' \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/12079"
```

### Assign Issue

```http
PATCH /repos/{owner}/{repo}/issues/{index}
```

**Request Body**:
```json
{
  "assignee": "your-username"
}
```

**Example**:
```bash
curl -X PATCH \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assignee": "your-username"}' \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/12079"
```

## Labels Reference

### Issue Type Labels

| Label | ID | Description |
|-------|-----|-------------|
| type/location-submission | 901 | New location submission |
| type/location-verification | 903 | Verification request |
| type/community-submission | 902 | Community/meetup submission |
| type/community-verification | 1464 | Community verification |
| type/location-removal | 904 | Removal request |

### Status Labels

| Label | ID | Description |
|-------|-----|-------------|
| status/pending | 1335 | Being processed |
| status/added | 1334 | Successfully added |
| status/rejected | 1333 | Rejected |

### Source Labels

| Label | ID | Description |
|-------|-----|-------------|
| import/square | 1307 | Imported from Square |

### Geographic Labels

Labels are organized by:
- **Country codes**: `us`, `gb`, `de`, `sv`, `ke`, etc.
- **Community names**: `bitcoin-beach`, `bitcoin-nairobi`, `bitcoin-berlin`
- **City/region**: `dallas-bitcoin`, `granada-2140`

## Rate Limits

Gitea API has the following limits:
- **Authenticated**: 300 requests per minute
- **Unauthenticated**: 60 requests per hour (not recommended)

**Best Practices**:
- Space requests at least 200ms apart
- Use pagination instead of large limits
- Cache responses when possible
- Handle 429 (Too Many Requests) with exponential backoff

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | OK | Success |
| 201 | Created | Comment/label added |
| 400 | Bad Request | Check request body |
| 401 | Unauthorized | Check token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Issue doesn't exist |
| 422 | Unprocessable | Validation error |
| 429 | Too Many Requests | Rate limited - wait and retry |

### Error Response Format

```json
{
  "message": "Error message",
  "url": "https://gitea.btcmap.org/api/swagger"
}
```

## Python Example

```python
import requests
import time

class GiteaAPI:
    def __init__(self, token, base_url='https://gitea.btcmap.org/api/v1'):
        self.token = token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/json'
        })
    
    def get_issues(self, repo='teambtcmap/btcmap-data', **params):
        """Fetch issues with filtering."""
        url = f"{self.base_url}/repos/{repo}/issues"
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        # Rate limiting
        time.sleep(0.2)
        
        return response.json()
    
    def post_comment(self, issue_number, body, repo='teambtcmap/btcmap-data'):
        """Post a comment to an issue."""
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        
        response = self.session.post(url, json={'body': body})
        response.raise_for_status()
        
        time.sleep(0.2)
        
        return response.json()
    
    def close_issue(self, issue_number, repo='teambtcmap/btcmap-data'):
        """Close an issue."""
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}"
        
        response = self.session.patch(url, json={'state': 'closed'})
        response.raise_for_status()
        
        return response.json()

# Usage
api = GiteaAPI(token='your-token-here')

# Fetch open issues
issues = api.get_issues(
    state='open',
    labels='type/location-submission',
    limit=10
)

# Post comment
api.post_comment(12079, "Verification complete: 90% confidence")

# Close issue
api.close_issue(12079)
```

## Testing

### Test Token

```bash
# Verify token works
curl -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.btcmap.org/api/v1/user"
```

### Test Issue Access

```bash
# Get a specific issue
curl -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/1"
```

### Test Comment Posting

```bash
# Post test comment (delete after)
curl -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "Test comment - please delete"}' \
  "https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/1/comments"
```

## References

- [Gitea API Swagger Docs](https://gitea.btcmap.org/api/swagger)
- [Gitea Documentation](https://docs.gitea.com/api)
- [Verification Workflow](VERIFICATION_WORKFLOW.md)
- [Example Issues](EXAMPLE_ISSUES.md)
