import datetime

import requests
from celery import shared_task
from django.conf import settings


@shared_task(bind=True)
def dispatch_request(self, data):
    req_id = data["id"]
    req_parent_id = data["parent_id"]
    req_status = data["status"]
    req_params = data["params"]
    req_created_at = data["created_at"]
    req_updated_at = data["updated_at"]

    query = """
        query GetUsers($paramsFilter: [JSONFilterInput!], $createdAt: DateTime!) {
          users(paramsFilter: $paramsFilter) {
            id
            params
            maxDailyRequests
            requestCount(status: "processed", createdAt: $createdAt)
          }
        }
    """

    variables = {
        "paramsFilter": [{"key": k, "value": v[0]} for k, v in req_params.items()],
        "createdAt": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    }

    response = requests.post(
        url=f"{settings.AIS_URL}/graphql/",
        json={
            "query": query,
            "variables": variables,
        }
    )

    response.raise_for_status()
    data = response.json()["data"]["users"]

    heights = [
        {
            "id": item["id"],
            "height": sum([v[1] * 1 if item["params"].get(k) else 0 for k, v in req_params.items()])
        } for item in data if
        item["maxDailyRequests"] is None or item["maxDailyRequests"] < item["requestCountByStatus"]
    ]

    most_relevant_user = max(heights, key=lambda height: height["height"])

    query = """
        mutation UpdateRequest($id: ID!, $userId: Int) {
          updateRequest(id: $id, userId: $userId) {
            request {
              id
            }
          }
        }
    """
    variables = {
        "id": int(req_id),
        "userId": int(most_relevant_user["id"])
    }

    _up = requests.post(
        url=f"{settings.AIS_URL}/graphql/",
        json={
            "query": query,
            "variables": variables,
        }
    )
    _up.raise_for_status()

    return int(most_relevant_user["id"])
