import re
from .prompts import order_template

def instruction_trigger(sender):
    # Check if the last message contains the path to the instruction text file
    return "instruction & resources saved to" in sender.last_message()["content"]


def instruction_message(recipient, messages, sender, config):
    # Extract the path to the instruction text file from the last message
    full_order = recipient.chat_messages_for_summary(sender)[-1]["content"]
    txt_path = full_order.replace("instruction & resources saved to ", "").strip()
    with open(txt_path, "r") as f:
        instruction = f.read() + "\n\nReply TERMINATE at the end of your response."
    return instruction


def order_trigger(sender, name, pattern):
    #print(f"[DEBUG] order_trigger: Checking if sender '{sender.name}' is '{name}' AND if pattern '{pattern}' is in the message.")
    return sender.name == name and pattern in sender.last_message()["content"]


def order_message(pattern, recipient, messages, sender, config):
    # Get the last message content from the leader agent
    leader_message_content = messages[-1].get("content", "")
    command_prefix = f"[{pattern}]:"
    extracted_order = None

    print("\n--- DEBUG: Inside order_message ---")
    print(f"Recipient (pattern): {pattern}")
    print(f"Leader's Full Message:\n---\n{leader_message_content}\n---")

    try:
        # Use regex to find agent command more robustly
        match = re.search(rf"\[{re.escape(pattern)}\]:\s*(.+)", leader_message_content, re.DOTALL)
        if match:
            extracted_order = match.group(1).strip()
            print(f"Successfully Extracted Order: '{extracted_order}'")
        else:
            print(f"WARNING: Could not find pattern '[{pattern}]:' in the message.")
    except Exception as e:
        print(f"ERROR parsing order: {e}")

    # Fallback if extraction fails
    if not extracted_order:
        raise ValueError(f"Leader did not provide a valid instruction for agent '{pattern}'")

    final_content = order_template.format(order=extracted_order)

    print("--- END DEBUG: Inside order_message ---\n")

    return {
        "content": final_content
    }