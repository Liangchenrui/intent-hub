import json
import os

# Define Intents and Samples
# Each intent has 5 clear, 40 standard, 5 boundary
intents_data = {
    "order_tracking": {
        "description": "Querying the current location or status of a shipment.",
        "clear": [
            "track my order", "where is my package", "order status", "check delivery status", "shipping update"
        ],
        "standard": [
            "Can you tell me where my parcel is?", "I want to see the tracking for my recent purchase.", 
            "When will my package arrive?", "Show me the progress of my shipment.", 
            "Is my order on its way?", "Provide a status update for order #12345.",
            "I'm looking for the tracking number of my last order.", "Check the delivery status of my shoes.",
            "How do I track my delivery?", "Where is my item currently located?",
            "Has my order been shipped yet?", "I haven't seen an update on my delivery in two days.",
            "What's the estimated arrival time for my order?", "Can I get a tracking link for my parcel?",
            "Is there a way to see where my order is right now?", "My tracking shows it's in transit, where is that?",
            "Status of my order please.", "Where is my package from yesterday?", "Track shipment for me.",
            "Information about my delivery.", "Where can I find my order tracking?", "Is my package at the local facility?",
            "I need an update on my order.", "Can you check my order's location?", "Where is my box?",
            "Any news on my shipping?", "Show my order progress.", "Track my recent shopping.",
            "Where is my stuff?", "Is my delivery near?", "Check on my order.", "Tracking info for my order.",
            "Status of package #9988.", "Has it arrived at my city yet?", "Where is the courier?",
            "I want to track my sneakers.", "Check my delivery status now.", "Update on my order status.",
            "Where's my order at?", "Status of the shipment."
        ],
        "boundary": [
            "My package is missing from the porch.", # Border with delivery_delay or loss
            "It says it arrived but I don't see it.", # Border with delivery_delay
            "Why is my order still in the warehouse?", # Border with delivery_delay
            "The tracking hasn't moved for three days.", # Border with delivery_delay
            "I'm worried about my order arrival." # Vague
        ]
    },
    "delivery_delay": {
        "description": "Reporting or inquiring about a late or delayed delivery.",
        "clear": [
            "my order is late", "delayed delivery", "package not arrived", "where is my late order", "delivery delay report"
        ],
        "standard": [
            "My order was supposed to be here yesterday.", "Why is my package taking so long?",
            "I haven't received my item yet and it's past the date.", "My delivery is significantly delayed.",
            "Where is my package? It is overdue.", "The delivery date has passed but I have nothing.",
            "Can you explain why my shipment is late?", "My order is stuck in transit for too long.",
            "I am still waiting for my package that was due last week.", "Why is my shipping taking forever?",
            "My order is late, what should I do?", "The estimated delivery was two days ago.",
            "I need help with a late delivery.", "Why hasn't my package arrived yet?",
            "Still no sign of my order.", "It's been a week and no package.",
            "Is there a problem with my delivery? It's late.", "Why is there a delay on my order?",
            "My package is overdue, where is it?", "I'm frustrated with this shipping delay.",
            "Can you check why my order is held up?", "The arrival date keeps changing.",
            "My delivery is late and I need it today.", "Where is my late shipment?",
            "I'm still waiting for my delivery.", "My package hasn't shown up yet.",
            "Why is my delivery taking more time than expected?", "I have not received my order yet.",
            "Where is my overdue parcel?", "The shipping is very slow this time.",
            "My package is stuck somewhere.", "Why is it late?", "Late delivery inquiry.",
            "My order is not here yet.", "Where's the late package?", "Check delay for me.",
            "Delivery time has passed.", "Why is my order still not here?", "Delayed shipping help.",
            "My order is behind schedule."
        ],
        "boundary": [
            "My tracking says it's still at the hub.", # Border with order_tracking
            "Where is my package? It's been a while.", # Border with order_tracking
            "I haven't seen an update in days.", # Border with order_tracking
            "Is my package lost or just slow?", # Border with loss/order_tracking
            "When will I actually get my stuff?" # Vague
        ]
    },
    "cancel_order": {
        "description": "Requesting to cancel an order that has not yet been processed or shipped.",
        "clear": [
            "cancel my order", "stop my order", "terminate order", "cancel recent purchase", "I want to cancel"
        ],
        "standard": [
            "I want to cancel order #55443.", "Can I stop my order before it ships?",
            "Please cancel my recent order.", "I changed my mind, cancel my purchase.",
            "I need to void my order.", "Is it too late to cancel my order?",
            "Cancel my sneakers order from today.", "I accidentally ordered twice, cancel one.",
            "Stop the shipment of my order please.", "I want to revoke my order.",
            "Can you cancel my order now?", "I need to cancel my latest shopping.",
            "Please stop my order processing.", "I don't want the item anymore, cancel it.",
            "I'd like to cancel my request.", "Can I cancel my order before it goes out?",
            "I want to cancel the order I just placed.", "Please cancel my order for the blue shirt.",
            "How do I cancel an order?", "I want to cancel my pending order.",
            "Stop my order from shipping.", "Cancel my purchase immediately.",
            "I need to cancel my order #1122.", "Can you help me cancel my order?",
            "I'm trying to cancel my order.", "Please don't ship my order, cancel it.",
            "I want to abort my order.", "Cancel my order today.", "I made a mistake, cancel the order.",
            "I want to cancel my transaction.", "Can I cancel?", "Please cancel it.", "Cancel order please.",
            "Stop the order.", "I want to cancel my buying.", "Don't send the order.", "Cancel my request.",
            "I need to cancel this.", "Cancel recent order.", "Stop shipment."
        ],
        "boundary": [
            "I don't want this anymore.", # Border with return_item
            "Can I get my money back for the order I just made?", # Border with refund_query
            "I want to return my order before it arrives.", # Border with return_item
            "Stop the process and refund me.", # Border with refund_query
            "I made a mistake on my order." # Vague
        ]
    },
    "return_item": {
        "description": "Inquiring about or initiating a return for a received product.",
        "clear": [
            "return my item", "how to return", "return policy", "send back product", "initiate a return"
        ],
        "standard": [
            "I want to return the shoes I bought.", "The item is damaged, I need to return it.",
            "How do I send back my order?", "I want to return this product for a refund.",
            "The shirt doesn't fit, can I return it?", "I need to return my recent purchase.",
            "What is your return process?", "Can I return an item I opened?",
            "I want to start a return.", "Where do I send returns?",
            "The product is not what I expected, I'm returning it.", "I'd like to return my order.",
            "How can I return this item?", "I want to return my parcel.",
            "Is it possible to return this?", "I need a return label.",
            "I want to return my order #7766.", "How do I return my sneakers?",
            "The quality is poor, I want to return it.", "I'm returning my recent buy.",
            "Can I return this within 30 days?", "I want to return the electronics.",
            "Help me with a return.", "Return policy for clothes.", "I want to send it back.",
            "Where is the return form?", "I need to return this gift.", "Return my package.",
            "I want to return my item.", "How to return a purchase.",
            "I'm sending this back.", "Can I return?", "Return help.", "I want to return.",
            "How to return it?", "Return my shoes.", "Send back the order.", "I want to return my dress.",
            "Return process please.", "I need to return."
        ],
        "boundary": [
            "I don't want this order anymore.", # Border with cancel_order
            "I want a refund for this product.", # Border with refund_query
            "Can I get my money back? The item is here.", # Border with refund_query
            "I changed my mind about the item I received.", # Border with cancel_order (logic-wise)
            "This item isn't right." # Vague
        ]
    },
    "payment_issue": {
        "description": "Reporting problems during the payment process or payment failures.",
        "clear": [
            "payment failed", "can't pay", "card declined", "payment error", "billing issue"
        ],
        "standard": [
            "My credit card was declined at checkout.", "I'm having trouble paying for my order.",
            "The payment page is not working.", "My payment keeps failing.",
            "Why was my transaction declined?", "I can't complete the payment.",
            "My payment method is not being accepted.", "There was an error during payment.",
            "I tried to pay but it didn't go through.", "Why can't I pay with my card?",
            "Help with a payment error.", "The checkout says my card is invalid.",
            "I'm getting a payment error message.", "My payment won't process.",
            "I can't pay for my items.", "Why is my payment failing?",
            "I'm stuck at the payment screen.", "The payment system is down.",
            "I keep getting a declined message.", "My billing info is correct but payment fails.",
            "I need help with a billing problem.", "Why did my payment fail?",
            "I can't finish my purchase because of a payment issue.", "The card payment is failing.",
            "My payment was rejected.", "Why can't I check out?", "Payment issue at checkout.",
            "I'm having a problem with my card.", "Payment not going through.",
            "I can't process my payment.", "Payment error.", "Failed transaction.",
            "Can't pay for my order.", "Card issue.", "Billing error.", "Checkout payment fail.",
            "Transaction error.", "I can't pay.", "Payment help.", "My card isn't working."
        ],
        "boundary": [
            "My money was taken but the order failed.", # Border with refund_query
            "I was charged twice.", # Border with refund_query
            "Can I pay with a different card?", # Border with payment_method_query
            "My card is blocked for this site.", # Border with account_access
            "I am worried about my transaction." # Vague
        ]
    },
    "refund_query": {
        "description": "Inquiring about the status of a refund or how to get a refund.",
        "clear": [
            "where is my refund", "refund status", "when will I get my refund", "how to get a refund", "refund update"
        ],
        "standard": [
            "I'm waiting for my refund to show up.", "When will I get my money back for my return?",
            "Can you check the status of my refund?", "How long does a refund take?",
            "I haven't received my refund yet.", "Is my refund processed?",
            "I returned my item, where is the refund?", "Show me my refund history.",
            "I'm looking for a refund on order #8877.", "Has my refund been issued?",
            "Why is my refund taking so long?", "I need an update on my refund.",
            "Where can I see my refund?", "How do I get my money back?",
            "I'm still waiting for my money.", "When will the refund reach my bank?",
            "I want a refund for my cancelled order.", "Has the money been refunded?",
            "Check my refund status please.", "I need my refund now.",
            "Where is my money?", "Refund for my order.", "I haven't got my refund.",
            "When is the refund coming?", "How to track my refund.", "Is my refund on the way?",
            "Refund inquiry.", "I'm waiting for a refund.", "Refund not received.",
            "Status of my refund.", "Where's the refund?", "Check refund.", "Refund help.",
            "When will I see the refund?", "Money back status.", "Refund for sneakers.",
            "Is the refund done?", "I need my money back.", "Refund question.", "Where is it?"
        ],
        "boundary": [
            "I was charged for an order I didn't make.", # Border with security_alert
            "My payment was a mistake, give it back.", # Border with payment_issue
            "I want to return this and get paid.", # Border with return_item
            "Why did you take my money?", # Border with payment_issue
            "I'm missing some money from my account." # Vague
        ]
    },
    "product_stock": {
        "description": "Checking if a specific product is currently available or in stock.",
        "clear": [
            "is it in stock", "product availability", "check stock", "is this item available", "stock check"
        ],
        "standard": [
            "Are these sneakers in stock?", "Is the blue shirt available in size M?",
            "Do you have this item in your warehouse?", "I want to check if this product is in stock.",
            "Is this product currently available?", "How many of these do you have left?",
            "Can you tell me if this is in stock?", "I'm looking for the availability of this watch.",
            "Is this item sold out?", "Do you have any more of these?",
            "I want to know if this is in stock.", "Is the stock level high for this?",
            "Check stock for me please.", "Is this item ready for shipping?",
            "Are there any units left?", "Is it available for purchase?",
            "I want to buy this, is it in stock?", "Check availability for order.",
            "Do you have this in stock?", "Is the item still in stock?",
            "Show me the stock for this.", "Is this available?", "In stock?",
            "Stock inquiry.", "Is this item here?", "Do you have it?", "Check stock levels.",
            "Is it sold out?", "Availability check.", "Any left in stock?",
            "Is it in stock now?", "Check if available.", "Is the item in store?",
            "Do you have more?", "Stock status.", "Is this still for sale?", "Can I buy this now?",
            "Is the item ready?", "Check stock.", "Available?"
        ],
        "boundary": [
            "When will this be back in stock?", # Border with restock_request
            "Notify me when this is ready.", # Border with restock_request
            "I want this but it says out of stock.", # Border with restock_request
            "Can I pre-order this item?", # Border with restock_request
            "Is this coming back soon?" # Vague
        ]
    },
    "restock_request": {
        "description": "Requesting to be notified when an out-of-stock item is back in stock.",
        "clear": [
            "notify me when in stock", "restock notification", "when will it be back", "restock request", "let me know when available"
        ],
        "standard": [
            "Can you notify me when the blue shirt is back?", "I want to be alerted when this is in stock.",
            "When will you restock these sneakers?", "Please let me know when this item is available again.",
            "Is there a waiting list for this item?", "I want a restock alert.",
            "When is the next shipment of these coming?", "Notify me for restock please.",
            "I'd like to be notified when this is back in stock.", "When will this be available for purchase again?",
            "Put me on the restock notification list.", "Can I get an email when this is back?",
            "I want to know when this is restocked.", "When are you getting more of these?",
            "Please alert me when it's back.", "When will it be restocked?",
            "I'm waiting for a restock of this.", "Tell me when this is in stock.",
            "Restock notification for size L.", "Can you email me for restock?",
            "When will this item return?", "I need a restock update.",
            "Alert me when this is available.", "When is the restock date?",
            "I want to be notified.", "Let me know when it's back.", "Restock alert.",
            "Notify me.", "When will it be back in stock?", "I want to know when it's here.",
            "Email me when available.", "When do you get more?", "Restock help.",
            "Notify when ready.", "Back in stock alert.", "When is it coming back?",
            "I'm waiting for restock.", "Can you notify me?", "When will you have it?", "Restock request."
        ],
        "boundary": [
            "Is this item out of stock permanently?", # Border with product_stock
            "I want to check if you have more coming.", # Border with product_stock
            "Can I buy this if it's not in stock yet?", # Border with product_stock
            "Will you ever have this again?", # Border with product_stock
            "I'm looking for a restock." # Vague
        ]
    },
    "account_access": {
        "description": "Dealing with login issues, password problems, or general account access.",
        "clear": [
            "can't login", "login issue", "password reset", "account access problem", "forgot password"
        ],
        "standard": [
            "I can't log into my account.", "I forgot my password, help.",
            "The login page is not working for me.", "My account is locked.",
            "I need to reset my password.", "Why can't I access my account?",
            "I'm having trouble with the login.", "Can you help me log in?",
            "I'm getting an error when I try to sign in.", "My login credentials are not working.",
            "I want to change my password.", "I can't remember my username.",
            "How do I unlock my account?", "I'm stuck at the login screen.",
            "The sign-in button is not responding.", "I need a password reset link.",
            "My account access is denied.", "Why is my account disabled?",
            "I can't log in on my phone.", "Help with my account login.",
            "I need to access my account settings.", "Where do I go to log in?",
            "I'm unable to sign into my profile.", "My login is failing.",
            "I need to update my password.", "How can I log in?", "Login help.",
            "I can't get in my account.", "Forgot my login.", "Password reset please.",
            "I can't sign in.", "Account locked.", "Reset my password.", "Login error.",
            "Sign in problem.", "I can't access my profile.", "Can't login now.",
            "Help with password.", "Forgot credentials.", "Login issue."
        ],
        "boundary": [
            "Is my account safe?", # Border with security_alert
            "Someone changed my password.", # Border with security_alert
            "I see a weird login on my account.", # Border with security_alert
            "Can I change my email for login?", # Border with security_alert
            "I'm worried about my account." # Vague
        ]
    },
    "security_alert": {
        "description": "Reporting suspicious activity, unauthorized access, or security concerns.",
        "clear": [
            "security alert", "unauthorized access", "suspicious activity", "hack report", "account security"
        ],
        "standard": [
            "I think my account was hacked.", "There is a suspicious login on my account.",
            "I didn't make this purchase, help!", "Someone else is using my account.",
            "I received a security alert email.", "My account has unauthorized activity.",
            "I want to report a security issue.", "I'm worried about my account safety.",
            "There's a login from a different country.", "I need to secure my account.",
            "Someone changed my account details.", "I suspect unauthorized access.",
            "Help, my account is compromised!", "I see a charge I didn't authorize.",
            "Is my account information safe?", "There is weird activity on my profile.",
            "I want to report a hack.", "My security was breached.",
            "Someone is trying to log into my account.", "I didn't change my password, but it's different.",
            "Unauthorized login detected.", "I need help with account security.",
            "My account was accessed by someone else.", "Check my account for security.",
            "I want to report fraud.", "Security concern with my account.", "Someone hacked me.",
            "Suspicious login.", "Unauthorized purchase.", "My account is not safe.",
            "Secure my account please.", "I think I was hacked.", "Unauthorized access help.",
            "Fraud alert.", "Security issue.", "Someone else logged in.", "Is my data safe?",
            "Report suspicious activity.", "Protect my account.", "Security alert."
        ],
        "boundary": [
            "I can't log in anymore, was I hacked?", # Border with account_access
            "I need to change my password for safety.", # Border with account_access
            "Why is my account locked for security?", # Border with account_access
            "I see a weird charge, is it a refund?", # Border with refund_query
            "Something is wrong with my account." # Vague
        ]
    }
}

# Generate train and test split
# 30 train, 20 test per intent
# Total 300 train, 200 test

raw_train_seq = []
raw_train_label = []
raw_test_seq = []
raw_test_label = []

processed_train = []
processed_test = []

id_counter = 1

for intent_name, data in intents_data.items():
    # Split each category
    # Clear: 5 -> 3 train, 2 test
    # Standard: 40 -> 24 train, 16 test
    # Boundary: 5 -> 3 train, 2 test
    
    train_utterances = data["clear"][:3] + data["standard"][:24] + data["boundary"][:3]
    test_utterances = data["clear"][3:5] + data["standard"][24:40] + data["boundary"][3:5]
    
    # Raw data
    for u in train_utterances:
        raw_train_seq.append(u)
        raw_train_label.append(intent_name)
    for u in test_utterances:
        raw_test_seq.append(u)
        raw_test_label.append(intent_name)
    
    # Processed data
    processed_train.append({
        "id": id_counter,
        "name": intent_name,
        "description": data["description"],
        "utterances": train_utterances
    })
    processed_test.append({
        "id": id_counter,
        "name": intent_name,
        "description": data["description"],
        "utterances": test_utterances
    })
    
    id_counter += 1

# Write Raw Data
with open("/root/lcr/intent-hub/exp/data/raw_data/ECOMMERCE_CONFLICT/train/seq.in", "w") as f:
    f.write("\n".join(raw_train_seq) + "\n")
with open("/root/lcr/intent-hub/exp/data/raw_data/ECOMMERCE_CONFLICT/train/label", "w") as f:
    f.write("\n".join(raw_train_label) + "\n")
with open("/root/lcr/intent-hub/exp/data/raw_data/ECOMMERCE_CONFLICT/test/seq.in", "w") as f:
    f.write("\n".join(raw_test_seq) + "\n")
with open("/root/lcr/intent-hub/exp/data/raw_data/ECOMMERCE_CONFLICT/test/label", "w") as f:
    f.write("\n".join(raw_test_label) + "\n")

# Write Processed Data
with open("/root/lcr/intent-hub/exp/data/processed_data/ECOMMERCE_CONFLICT/for_intent_hub/train.json", "w") as f:
    json.dump(processed_train, f, indent=2)
with open("/root/lcr/intent-hub/exp/data/processed_data/ECOMMERCE_CONFLICT/for_intent_hub/test.json", "w") as f:
    json.dump(processed_test, f, indent=2)

print("Dataset ECOMMERCE_CONFLICT generated successfully.")
