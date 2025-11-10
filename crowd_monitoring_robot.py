import cv2
import time
import threading
from twilio.rest import Client
from playsound import playsound
import mediapipe as mp
import torch

# --- 1. TWILIO SETUP ---
account_sid = "AC86ebe2adf08a8a7adcd117beec26bcd3"
auth_token = "9843f2ce203de63c4f7e3c0921b3e0a8"
twilio_number = "+15513219712"
my_phone_number = "+919849652269"

client = Client(account_sid, auth_token)

# --- 2. ALERT FUNCTION ---
def send_sms_alert(message_body):
    try:
        message = client.messages.create(
            to=my_phone_number,
            from_=twilio_number,
            body=message_body
        )
        print(f"SMS sent successfully! SID: {message.sid}")
    except Exception as e:
        print(f"Error sending SMS: {e}")

# --- 3. ALARM FUNCTION ---
def play_alarm():
    try:
        playsound('alarm.mp3')
    except Exception as e:
        print(f"Error playing alarm sound: {e}")

# --- 4. LOAD YOLOv5 MODEL (auto-download yolov5s.pt if missing) ---
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
classes = model.names

# --- 5. MEDIAPIPE SETUP ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

# --- 6. CROWD MONITORING LOGIC ---
def analyze_crowd(frame):
    # --- YOLOv5 DETECTION ---
    results = model(frame)
    detected_objects = results.pandas().xyxy[0]['name'].tolist()

    # --- MEDIAPIPE POSE ANALYSIS ---
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results_pose = pose.process(rgb_frame)

    close_contact = False
    if results_pose.pose_landmarks:
        landmarks = results_pose.pose_landmarks.landmark
        left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
        wrist_distance = abs(left_wrist.x - right_wrist.x)

        if wrist_distance < 0.05:  # threshold → people too close / possible struggle
            close_contact = True

    # --- Decision Logic ---
    if "knife" in detected_objects or "gun" in detected_objects:
        return "danger"
    elif ("person" in detected_objects and detected_objects.count("person") > 3) or close_contact:
        return "harassment"
    else:
        return "safe"

# --- 7. MAIN LOOP ---
def main():
    print("Camera feed active. Press 'q' to exit.")

    ip_url = "http://192.168.1.5:8080/video"   # Replace with your phone's IP Webcam URL
    cap = cv2.VideoCapture(ip_url)

    if not cap.isOpened():
        print("Error: Could not open camera stream.")
        return

    last_alert_time = 0
    cooldown = 15  # seconds

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame.")
            break

        status = analyze_crowd(frame)

        if status == "safe":
            cv2.putText(frame, "Crowd is Safe ✅", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            print("✅ Crowd is safe")
            if time.time() - last_alert_time > cooldown:
                send_sms_alert("✅ Crowd is safe.")
                last_alert_time = time.time()

        elif status == "danger":
            cv2.putText(frame, "⚠️ DANGER DETECTED!", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            print("⚠️ Danger detected! Sending SMS alert...")
            if time.time() - last_alert_time > cooldown:
                send_sms_alert("⚠️ Danger detected! Possible weapon/fight.")
                threading.Thread(target=play_alarm).start()
                last_alert_time = time.time()

        elif status == "harassment":
            cv2.putText(frame, "🔴 HARASSMENT DETECTED!", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            print("🔴 Harassment detected! Sending SMS alert...")
            if time.time() - last_alert_time > cooldown:
                send_sms_alert("🔴 Harassment detected! Urgent attention needed.")
                threading.Thread(target=play_alarm).start()
                last_alert_time = time.time()

        cv2.imshow("Crowd Monitoring Feed", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Program terminated.")

# --- 8. RUN ---
if _name_ == "main":
    main()
