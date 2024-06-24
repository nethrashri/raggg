import sqlite3
import streamlit as st
from langchain_community.llms import Ollama
import json

# Function to load the model using Ollama
@st.cache_resource
def load_my_model():
    try:
        llm = Ollama(model="mistral:7b-instruct-q6_K")
        return llm
    except Exception as e:
        st.error(f"Error loading model: {e}")
        return None

llm = load_my_model()

# Function to query the home_details.db for available devices
def get_available_devices(hashid):
    query = "SELECT Hashid, LocationName, devicefriendName, macid, clusterid, devicetype FROM home_details WHERE Hashid = ?"
    with sqlite3.connect('home_details.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, (hashid,))
        devices = cursor.fetchall()
    # Debugging: Print the fetched devices
    st.write("Fetched Devices:", devices)
    return devices

# Function to generate the prompt based on the routine type and available devices
def generate_prompt(routine_type, hashid, devices):
    example_output = """
[
  {
    "routine_name": "morning",
    "devicetype": "light",
    "room_name": "bed room",
    "macid": "23213234",
    "time": "06:00",
    "status": "on",
    "com": [
      {
        "supportedclusid": 6,
        "supportedclus_val": "true"
      },
      {
        "supportedclusid": 8,
        "supportedclusid_val": 70,
        "saturation": 128
      }
    ]
  },
  {
    "routine_name": "morning",
    "devicetype": "motion sensor",
    "room_name": "bed room",
    "macid": "23213237",
    "time": "06:15",
    "status": "off",
    "com": [
      {
        "supportedclusid": 6,
        "supportedclus_val": "false"
      }
    ]
  },
  {
    "routine_name": "morning",
    "devicetype": "thermostat",
    "room_name": "bed room",
    "macid": "232132378",
    "time": "06:30",
    "status": "on",
    "com": [
      {
        "supportedclusid": 6,
        "supportedclus_val": "true"
      }
    ]
  },
  {
    "routine_name": "morning",
    "devicetype": "smart blinds",
    "room_name": "bed room",
    "macid": "232132399",
    "time": "06:45",
    "status": "off",
    "com": [
      {
        "supportedclusid": 6,
        "supportedclus_val": "false"
      }
    ]
  }
]
"""

    context = f"""
You are a smart home assistant. You understand and control smart devices within a home environment, create routines, and show available devices in the home.

Humans, referred to as users, engage in various activities throughout their day. They live in homes equipped with multiple devices and follow different routines such as morning routines, evening routines, movie time routines, and party time routines. Each routine involves the use of specific devices in different rooms at specific times.

Imagine you are like Alexa, a smart home virtual assistant, providing suggestions for creating these routines. You need to check for available devices in the user's home and create routines based on the time and device mapping in the home_details.db.

For light devices, consider the following:
- When the status is 'on' or 'off', include a `supportedclusid` of 6 with a `supportedclus_val` of 'true' or 'false'.
- Suggest brightness when `supportedclusid` is 8, with `supportedclusid_val` between 0-100 (which represents brightness).
- Include saturation values ranging from 0-256.

For thermostat and other devices, consider the following:
- Include only `supportedclusid` 6 with a `supportedclus_val` based on the status ('true' for on/open/up, 'false' for off/close/down).

Here are the available devices in the home of user with Hashid {hashid}: {devices}

Create a {routine_type} routine for the user with Hashid {hashid} in the following JSON format. Make sure to replace any placeholders like 'brightness_value' with actual values:
{example_output}
"""

    # Debugging: Print the generated prompt
    st.write("Generated Prompt:", context)

    return context

# Main function to create the routine
def create_routine(hashid, routine_type):
    devices = get_available_devices(hashid)
    if not devices:
        return "No devices found for the given Hashid."

    # Transform clusterid from string to list
    transformed_devices = []
    for device in devices:
        device = list(device)
        try:
            device[4] = json.loads(device[4])  # Convert clusterid from JSON string to list
        except json.JSONDecodeError as e:
            st.error(f"Error decoding clusterid for device {device[2]}: {e}")
            continue
        transformed_devices.append(tuple(device))
    
    prompt = generate_prompt(routine_type, hashid, transformed_devices)
    
    # Use Ollama to generate response
    try:
        response = llm(prompt)
        # Debugging: Print the raw response from the LLM
        st.write("Raw Response from LLM:", response)
    except Exception as e:
        st.error(f"Error while generating response: {e}")
        return "No response from the model due to an error."

    # Handle and format the response from the model
    try:
        if isinstance(response, str) and response.strip():
            response_text = response.strip()
            st.write("Model Response Raw:")
            st.text_area("Response:", response_text, height=300)
            
            # Parse the JSON response
            try:
                parsed_data = json.loads(response_text)
                
                # Save to JSON file
                with open(f'{routine_type}_routine.json', 'w') as json_file:
                    json.dump(parsed_data, json_file, indent=4)
                
                st.write("Routine saved to JSON file.")
                return json.dumps(parsed_data, indent=4)
            except json.JSONDecodeError as e:
                return f"Unexpected response format from the model: {e}"
        else:
            return "No response from the model."
    except Exception as e:
        return f"Unexpected error occurred: {e}"

# Streamlit UI
st.title("Home Routine Suggestion")

hashid = st.text_input("Enter User Hashid:")
routine_type = st.text_input("Enter Routine Type (e.g., morning, evening, party time, movie time):")

if st.button("Generate Routine"):
    if hashid and routine_type:
        with st.spinner('Generating routine...'):
            routine_suggestion = create_routine(hashid, routine_type)
        st.text(routine_suggestion)
    else:
        st.warning("Please enter both a Hashid and a routine type.")
