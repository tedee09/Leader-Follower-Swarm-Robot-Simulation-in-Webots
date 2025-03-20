#robot2 as follower sebelum edit
from controller import Robot, Camera
import random
import math
import json

TIME_STEP = 64
FOLLOW_DISTANCE = 0.5  # Jarak tetap di belakang `robot1`

# Inisialisasi robot dan timestep
robot = Robot()
timestep = int(robot.getBasicTimeStep())

# Inisialisasi aktuator (motor)
motor_kanan_depan = robot.getDevice("motor_kanan_depan")
motor_kanan_belakang = robot.getDevice("motor_kanan_belakang")
motor_kiri_depan = robot.getDevice("motor_kiri_depan")
motor_kiri_belakang = robot.getDevice("motor_kiri_belakang")

# Atur mode motor ke velocity
motors = [motor_kanan_depan, motor_kanan_belakang, motor_kiri_depan, motor_kiri_belakang]
for motor in motors:
    motor.setPosition(float('inf'))  # Non-positional mode
    motor.setVelocity(0.0)          # Awalnya berhenti

# Inisialisasi sensor jarak (distance sensor)
ds_depan = robot.getDevice("ds_depan")
ds_kanan = robot.getDevice("ds_kanan")
ds_kiri = robot.getDevice("ds_kiri")
ds_belakang = robot.getDevice("ds_belakang")
distance_sensors = [ds_depan, ds_kanan, ds_kiri, ds_belakang]

# Aktifkan semua sensor jarak
for ds in distance_sensors:
    ds.enable(timestep)

# Inisialisasi GPS dan IMU
gps = robot.getDevice("global")
gps.enable(timestep)

imu = robot.getDevice("imu")
imu.enable(timestep)

# Inisialisasi kamera
camera = robot.getDevice("cam")
camera.enable(timestep)
camera.recognitionEnable(TIME_STEP)
camera_width = camera.getWidth()
camera_height = camera.getHeight()

# Inisialisasi emitter
emitter = robot.getDevice("emitter")
emitter.setChannel(1)  # Channel broadcast

# Inisialisasi receiver
receiver = robot.getDevice("receiver")
receiver.setChannel(1)  # Channel broadcast
receiver.enable(timestep)

#focal length dan ukuran objek (cuma nebak aja njir)
focal_length = 1000
known_size = 0.0000137

chosen_direction = None # Variabel untuk menyimpan arah putar saat menghadapi rintangan

# Fungsi untuk mengatur kecepatan motor
def set_motor_velocity(left_speed, right_speed):
    motor_kiri_depan.setVelocity(left_speed)
    motor_kiri_belakang.setVelocity(left_speed)
    motor_kanan_depan.setVelocity(right_speed)
    motor_kanan_belakang.setVelocity(right_speed)
    
def is_red(color_array):
    r, g, b = color_array[0], color_array[1], color_array[2]
    return abs(r - 1.0) < 0.1 and abs(g - 0.0) < 0.1 and abs(b - 0.0) < 0.1
    
def calculate_distance(apparent_size):
    if apparent_size > 0:
        distance = (focal_length * known_size) / apparent_size
        return distance
    return None

# Fungsi menghitung jarak Euclidean
def euclidean_distance(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

# Fungsi menghitung sudut ke target
def get_angle_to_target(current_pos, target_pos):
    delta_x = target_pos[0] - current_pos[0]
    delta_y = target_pos[1] - current_pos[1]
    return math.atan2(delta_y, delta_x)

# Fungsi untuk menghitung posisi "belakang" dari pengirim
def calculate_follow_position(sender_x, sender_y, yaw, distance=1.0):
    follow_x = sender_x - distance * math.cos(yaw)
    follow_y = sender_y - distance * math.sin(yaw)
    return follow_x, follow_y

# Program utama
def main():
    angle_kp = 2.0
    max_speed = 8.0
    follow_distance = 1.5  # Jarak yang ingin dijaga di belakang pengirim
    min_distance_to_stop = 0.3  # Jarak minimum ke target sebelum berhenti

    target_x, target_y = None, None

    global chosen_direction # variabel global untuk menyimpan arah putar

    while robot.step(timestep) != -1:
        if receiver.getQueueLength() > 0:
            message = receiver.getString()
            data = json.loads(message)
            sender_x, sender_y, sender_yaw = data["x"], data["y"], data["yaw"]
            receiver.nextPacket()

            # Hitung posisi "belakang" pengirim
            target_x, target_y = calculate_follow_position(sender_x, sender_y, sender_yaw, follow_distance)
            print(f"[Receiver] Target posisi di belakang pengirim: ({target_x}, {target_y})")

        if target_x is None or target_y is None:
            print("[Receiver] Menunggu data posisi dari pengirim...")
            continue

        # Ambil posisi penerima
        current_pos = gps.getValues()
        current_x = current_pos[0]
        current_y = current_pos[1]
        current_angle = imu.getRollPitchYaw()[2]

        # Baca data sensor jarak
        depan_value = ds_depan.getValue()
        kanan_value = ds_kanan.getValue()
        kiri_value = ds_kiri.getValue()
        belakang_value = ds_belakang.getValue()

        recognized_objects = camera.getRecognitionObjects()
        red_detected = False
        distance_to_object = None

        distance_to_target = euclidean_distance([current_x, current_y], [target_x, target_y])
        angle_to_target = get_angle_to_target([current_x, current_y], [target_x, target_y])
        angle_error = angle_to_target - current_angle

        angle_error = (angle_error + math.pi) % (2 * math.pi) - math.pi

        if distance_to_target < min_distance_to_stop:
            continue

        correction = angle_kp * angle_error
        left_speed = 6.0 - correction
        right_speed = 6.0 + correction

        left_speed = max(min(left_speed, max_speed), -max_speed)
        right_speed = max(min(right_speed, max_speed), -max_speed)

        set_motor_velocity(left_speed, right_speed)
        
        for obj in recognized_objects:
            color_array = obj.getColors()
            
            if is_red(color_array):
                red_detected = True
                object_position_x, object_position_y = obj.getPositionOnImage()
                apparent_size = obj.getSize()[0] # Ukuran objek di gambar (dalam piksel)
                distance_to_object = calculate_distance(apparent_size)
                if distance_to_object is not None:
                    pass
            
        if red_detected and distance_to_object is not None:
            left_bound = camera_width * 0.4
            right_bound = camera_width * 0.6
            top_bound = camera_height * 0.29  
            middle_bound = camera_height * 0.66
            
            if left_bound <= object_position_x <= right_bound:
                if object_position_y < top_bound:
                    print("Objek di tengah atas, berhenti")
                    set_motor_velocity(0.0, 0.0)  # Berhenti
                    if object_position_y <= camera_height * 0.25:
                        print("inih")
                        set_motor_velocity(-6.0, -6.0)
                elif top_bound <= object_position_y <= middle_bound:
                    print("Objek di tengah vertikal")
                    set_motor_velocity(6.0, 6.0)  # Maju lurus
                else:
                    print("Objek di tengah bawah")
                    set_motor_velocity(5.0, 5.0)  # Maju lebih cepat
            elif object_position_x < left_bound:
                print("Objek di kiri, coba ngiri")
                set_motor_velocity(-3.0, 4.0)
                
                if depan_value < 1000:
                    print("ini wak")
                    set_motor_velocity(-4.0, -4.0)
            elif object_position_x > right_bound:
                print("Objek di kanan, coba nganan")
                set_motor_velocity(4.0, -3.0)
                
                if depan_value < 1000:
                    set_motor_velocity(-4.0, -4.0)
            else:
                pass          
                            
        elif depan_value < 1000:  # Jika ada rintangan di depan
            if chosen_direction  is None: # Pilih arah hanya sekali
                chosen_direction  = random.choice(["left", "right"])
            
            if chosen_direction  == "left":
                set_motor_velocity(-6.0, 6.0)  # Berputar
            else:
                set_motor_velocity(6.0, -6.0)  # Berputar
        elif kiri_value < 1000:  # Jika ada rintangan di kiri
            set_motor_velocity(6.0, 4.5)  # Belok kanan
        elif kanan_value < 1000:  # Jika ada rintangan di kanan
            set_motor_velocity(4.5, 6.0)  # Belok kiri
        
if __name__ == "__main__":
    main()