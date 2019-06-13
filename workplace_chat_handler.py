import os, sys

sys.path.insert(0, os.path.join(os.getcwd(), "dependencies"))

import json
import boto3
import requests
from fbmq import Attachment, Template, QuickReply, Page  # https://github.com/conbus/fbmq

WORKPLACE_VERIFY_TOKEN = "any_token"
PAGE_ACCESS_TOKEN = "DQVJ0NTNZAb21PenZAUM25EMnFrRzV0Mk5wMTY5WWFXa2JXQ0wwWXdUMUQ3bXJjdEJQUGhsUXduQUdGZAkpqdU5sWENneHhlcWN5MkNFSnVBa2pUMEJRd2JReGxlTURtTmVzRTZAtSzZAFVWd3ZA1NfXzF5TXZAOVjNEMmd1TG9vZA1NDVTlnVE5TaHpsZA0NYbWpUOWJ4OXR2MDBSOGZARb1R3eWpOUl9iTmRwWHlGV3pTVGZA0anhXYmRvaVF2eXNmUk9PeHhfZAVJzSGxfai1obFNCYjhyeAZDZD"


def lambda_handler(event, context):
    print("Received event:\n", json.dumps(event))
    body = json.loads(event["body"])
    print("Request body:", json.dumps(body))
    error_object = None

    # Handling GET requests
    if event["httpMethod"] == "GET":
        query_params = event["queryStringParameters"]
        # If this is a verification call from Workplace by Facebook
        if "hub.verify_token" in query_params and 'hub.verify_token' in query_params:
            return subscribe_bot(query_params)

    # If this message is from a page subscription
    if body["object"] == "page":
        # For each page entry
        # There may be multiple entries if multiple lines were sent from chat in one batch
        for entry in body['entry'][-1:]:
            for message_object in entry["messaging"]:
                if 'message' in message_object:
                    return received_message(message_object)
                elif 'postback' in message_object:
                    return received_postback(message_object)
                else:
                    error_object = message_object
                    print('Webhook received unknown messagingEvent: ', message_object)
    # Assume all went well.
    # You must send back a 200, within 20 seconds, to let Facebook know the request was
    # successfully received. Otherwise, the request will time out and be repeated forever.
    return {'body': 'Received unkown request' + json.dumps(error_object),
            'statusCode': 200}


# Message Event

# This event is called when a message is sent to your page. The 'message'
# object format can vary depending on the kind of message that was received.
# Read more at https://developers.facebook.com/docs/messenger-platform/webhook-reference/message-received

# For this example, we're going to echo any text that we get.
def received_message(event):
    sender_id = event["sender"]["id"]
    chat_message = event["message"]
    chat_message['sender_id'] = sender_id
    print("Message for Boost:", chat_message)

    # Buttons list
    buttons = []

    # Call WorkPlace with the sender_id to get the employee ID later used to get tjenestebevis
    # IMPORTANT: Department is the test replacement for Employee ID as this field is not available yet
    wp_url = "https://graph.facebook.com/v3.1/"+sender_id
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "department"
    }
    wp_response = requests.get(wp_url, params=params)
    print("WP response URL:", wp_response.url)
    print("WP response:", wp_response.json())
    wp_response = wp_response.json()
    if "department" in wp_response:
        employee_id = wp_response['department']
        print("Employee ID: ",employee_id)
    else:
        employee_id = '00000000'
        print("Employee ID missing, set default value:",employee_id)

    # Call Boost AI handler function to get intent and response message
    print("Payload for Boost.ai: ", json.dumps(chat_message))
    boto3_client = boto3.client('lambda')
    boostai_response = boto3_client.invoke(
        FunctionName='uke-chatbot-poc-BoostAiHandler-1QLZKO8EUY95I',
        InvocationType='RequestResponse',
        Payload=json.dumps(chat_message)
    )
    boostai_payload = json.loads(boostai_response['Payload'].read().decode("utf-8"))

    print("BoostAI returned:", json.dumps(boostai_payload))
    page = Page(PAGE_ACCESS_TOKEN)
    if "skill" in boostai_payload['conversation']['state']:
        # skill = intent from Boost.ai
        intent = boostai_payload['conversation']['state']['skill']
    if "id" in boostai_payload['conversation']:
        # save conversation id for use with buttons
        conv_id = boostai_payload['conversation']['id']

    # Get user profile
    # user_profile = page.get_user_profile(sender_id) # return dict
    # print(user_profile)
    # Through Workplace Graph API
    # user_info_response = requests.(workplace_https, headers=workplace_headers, data='{"?"}')
    if "response" in boostai_payload:
        for message in boostai_payload["response"]["elements"]:
            if "text" in message["payload"]:
                # TODO update this temp solution for KB integration with skill keyword from Boost
                if message["payload"]["text"] == "Jeg forstår dessverre ikke spørsmålet ditt.":
                    return knowledgebase_query(sender_id,
                                               {"chat_message": chat_message, "boost_payload": boostai_payload})
                else:
                    print("Sending TEXT message to Workplace chat")
                    page.send(sender_id, message["payload"]["text"])
            elif "links" in message["payload"]:
                for link in message["payload"]["links"]:
                    if link["type"] == 'action_link':
                        if 'employee_id' in locals() or 'employee_id' in globals():
                            # if button is pushed, send button ID, sender ID, and previous intent to Boost
                            buttons.append(QuickReply(link["text"], link["id"] + ";" + sender_id + ";" + intent + ";" + conv_id + ";" + employee_id))
                        else:
                            buttons.append(QuickReply(link["text"], link["id"] + ";" + sender_id + ";" + intent + ";" + conv_id))
                    else:
                        print("Sending LINK message to Workplace chat")
                        page.send(sender_id, link['url'])
                print("Sending LINKTEXT message to Workplace chat")
                page.send(sender_id, "Dine valg:", quick_replies=buttons, metadata="Metadata TBD")
    elif "errorMessage" in boostai_payload:
        message = boostai_payload["errorMessage"]
        page.send(sender_id, "Boost.ai returnerte feilmelding: " + message)

    return {'body': json.dumps({"sender_id": sender_id, "message": message}),
            'statusCode': 200}


# Postback Event

# This event is called when a postback is tapped on a Structured Message.
# This function will be called if the user clicks a button in chat for instance
# https://developers.facebook.com/docs/messenger-platform/webhook-reference/postback-received
def received_postback(event):
    sender_id = event["sender"]["id"]
    recipient_id = event["recipient"]["id"]

    # The 'payload' param is a developer-defined field which is set in a postback
    # button for Structured Messages.
    payload = event.postback.payload
    # Embed extra info int he payload in the format ACTION:OBJECT
    tokens = payload.split(':')
    action = tokens[0]
    object = tokens[1]

    # When a postback is called, we'll send a message back to the sender to
    # let them know it was successful
    # TODO Implement logic for postbacks
    # if action == 'ORDER_PROOF_OF_SERVICE':
    #     removeClaim(object)
    #     sendOpenClaims(senderID)
    # elif action == 'BUTTON_CLICKED':
    #     rejectClaim(senderID,object)
    # else:
    #     sendTextMessage(senderID, 'Postback called: ' + payload);

    return {'body': 'Confirming object == postback',
            'statusCode': 200}


def knowledgebase_query(recipient_id, query):
    print("Knowledgebase will be sent query payload:\n", query)
    # Invoke Knowledgebase handler to send query to Watson Explorer
    boto3_client = boto3.client('lambda')
    wex_response = boto3_client.invoke(
        FunctionName='uke-chatbot-poc-knowledgebaseHandler-134TF41W7EW3I',
        InvocationType='RequestResponse',
        Payload=json.dumps(query)
    )
    print("Knowledgebase responded with:\n", wex_response)
    wex_payload = json.loads(wex_response['Payload'].read().decode("utf-8"))
    print("KB returned payload:\n", wex_payload)

    # Construct a card object per article returned by knowledgebase that should be shown to user
    buttons = []
    kb_response = wex_payload['body']["response"]
    docs = kb_response["docs"]
    highlights = wex_payload['body']["highlighting"]
    print("Knowledgebase returned ", len(docs), "documents")

    for i in range(len(docs)):
        print("Message:", docs[i]["title"][0])  # ["content"])
        print("Highlight", highlights[docs[i]["id"]]["views"]["body"][0]["content"])
        buttons.append(Template.GenericElement(docs[i]["title"][0],
                                               subtitle=highlights[docs[i]["id"]]["views"]["body"][0]["content"],
                                               item_url=docs[i]["_source"][0],
                                               image_url="https://www.vartoslo.no/media/uploads/2019/02/oslo_kommune_logo.png"
                                               )
                       )

    # Send cards with article URL to Workplace
    page = Page(PAGE_ACCESS_TOKEN)
    if not docs:
        print("Sending KB_TEXT message to Workplace chat with recipient_id:", recipient_id)
        # If there are no documents, send an apology to user
        wp_response = page.send(recipient_id,
                                "Beklager men jeg fant ingen dokumenter som kan svare på spørsmålet ditt: \n\"" +
                                query["chat_message"]["text"] + "\"")
        print("Sending first KB_TEXT to WP recipient:", recipient_id, "resulting in response:\n", wp_response)
        wp_response = page.send(recipient_id, "Kan du prøve å stille spørsmålet på en annen måte?")
        print("Sending second KB_TEXT to WP recipient:", recipient_id, "resulting in response:\n", wp_response)
    else:
        print("Sending KB_CARDS message to Workplace chat with recipient_id:", recipient_id)
        # If there are documents, send the cards to chat
        page.send(recipient_id, "Svarer noen av disse artiklene på spørsmålet ditt?")
        wp_response = page.send(recipient_id, Template.Generic(buttons))
        print("WP responded with:", wp_response.json())

    return {
        'body': 'Knowledgebase queried and returned status code',
        'statusCode': wex_payload["statusCode"]
    }


def subscribe_bot(query_params):
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if query_params["hub.mode"] == "subscribe" and query_params["hub.challenge"]:
        if not query_params["hub.verify_token"] == WORKPLACE_VERIFY_TOKEN:
            return {"statusCode": 403,
                    "headers": {"Content-Type": "application/json"},
                    "body": "{\"message\": \"Verification token mismatch\"}"}
        return {'body': query_params["hub.challenge"],
                'statusCode': 200}

    return {"statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": "{\"message\": \"Unsuported parameters\"}"}
