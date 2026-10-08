from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random
import time

# ===== window / world numbers =====
window_width, window_height = (1000, 800) # window size
fov_y = 90 # camera view width
num_lanes = 21 # how many lanes
lane_width = 180 # space between lanes
row_spacing = 220 # space between rows
building_size = 140 # building size
min_height = 80 # shortest building
max_height = 260 # tallest building
rows_ahead = 12 # rows built ahead

# ===== time (delta time) =====
last_time = time.time() # last clock check
delta_time = 0.0 # time since last frame

# ===== player =====
player_row = 0 # player's row
player_lane = 1 # player's lane
player_x = 0.0 # player x position
player_y = 0.0 # player y position
player_z = 0.0 # player height
player_is_jumping = False # true if jumping
jump_progress = 0.0 # jump progress, 0 to 1
jump_start_x, jump_start_y, jump_start_z = (0.0, 0.0, 0.0) # jump start point
jump_target_x, jump_target_y, jump_target_z = (0.0, 0.0, 0.0) # jump end point
jump_target_row = 0 # row to land on
jump_target_lane = 1 # lane to land on
jump_time = 0.4 # jump time, seconds
jump_hop_height = 60 # how high the hop goes

# ===== player body proportions =====
player_leg_height = 35 # leg height
player_torso_height = 52 # body height
player_head_radius = 14 # head size
player_shoulder_x = 19 # shoulder width
player_shoulder_z = player_torso_height - 8 # shoulder height
player_arm_length = 55 # arm length
player_arm_radius = 6 # arm thickness
player_hand_radius = 7 # hand size

# ===== city =====
buildings = {} # all buildings

# ===== enemies =====
enemies = {} # all enemies
enemy_chance = 0.35 # chance of enemy
enemy_speed = 60 # enemy speed
player_hit_range = 40 # enemy hit distance

# ===== webs =====
webs = [] # webs flying now
web_speed = 500 # web speed
web_cooldown_time = 0.3 # time between shots
web_cooldown = 0.0 # time left to shoot again
enemy_hit_range = 30 # web hit distance

# ===== rescue =====
victim_row = None # victim's row
victim_lane = None # victim's lane
victim_gap_min = 3 # smallest victim gap
victim_gap_max = 8 # biggest victim gap
next_victim_row = random.randint(victim_gap_min, victim_gap_max) # next victim row
victim_start_row = None # row when victim came
rescue_window = 6 # rows to save victim
failed_rescues = 0 # missed victims
max_failed_rescues = 3 # max misses allowed

# ===== score / progress =====
kill_score = 0 # points from kills
kill_streak = 0 # kills in a row
rescue_score = 0 # points from rescues
rows_crossed = 0 # rows passed

# ===== combo scoring =====
score_multiplier = 1 # point multiplier
max_multiplier = 5 # max multiplier
streak_per_multiplier = 3 # kills per level up
kill_base_points = 10 # points per kill
rescue_base_points = 50 # points per rescue

# ===== lives / game state =====
player_lives = 3 # lives now
max_lives = 3 # max lives
game_over = False # true if game ended

# ===== camera =====
camera_mode = 0 # 0=third, 1=first, 2=top
camera_angle = 0.0 # camera angle
camera_height = 300.0 # camera height
camera_radius = 350.0 # camera distance
camera_angle_speed = 60.0 # angle change speed
camera_height_speed = 150.0 # height change speed

# ===== camera effects (shake + smoothing) =====
camera_shake = 0.0 # shake amount
smooth_x = None # smooth camera x
smooth_y = None # smooth camera y
smooth_z = None # smooth camera z

# ===== cheat mode =====
cheat_mode = False # true if cheat on
cheat_timer = 0.0 # time to next auto jump
cheat_jump_gap = 0.6 # time between auto jumps
camera_look_angle = 0.0 # first person look angle
camera_look_turn_speed = 4.0 # how fast it turns

# ===== heart pickups (extra lives) =====
heart_row = None # heart's row
heart_lane = None # heart's lane
heart_gap_min = 5 # smallest heart gap
heart_gap_max = 15 # biggest heart gap
next_heart_row = random.randint(heart_gap_min, heart_gap_max) # next heart row


################################################################################
# main
################################################################################
def distance2d(x1, y1, x2, y2):
    # find distance
    return math.hypot(x2 - x1, y2 - y1)

def lane_x(lane):
    # lane to x position
    return (lane - (num_lanes - 1) / 2) * lane_width

def row_y(row):
    # row to y position
    return row * row_spacing

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18): #type: ignore
    # draw text on screen
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, window_width, 0, window_height)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
################################################################################
# world_player
################################################################################
def check_and_place_heart():
    # add heart if it's time
    global heart_row, heart_lane
    if heart_row is None and (next_heart_row, 0) in buildings:
        heart_row = next_heart_row
        heart_lane = random.randint(0, num_lanes - 1)
heart_window = 10 # rows to reach heart

def check_heart_pickup():
    # check if heart caught or missed
    global heart_row, heart_lane, next_heart_row, player_lives
    if heart_row is not None and (player_row, player_lane) == (heart_row, heart_lane):
        # caught it, add a life
        player_lives = min(player_lives + 1, max_lives)
        heart_row = None
        heart_lane = None
        next_heart_row = rows_crossed + random.randint(heart_gap_min, heart_gap_max)
    elif heart_row is not None and rows_crossed - heart_row > heart_window:
        # missed it, remove it
        heart_row = None
        heart_lane = None
        next_heart_row = rows_crossed + random.randint(heart_gap_min, heart_gap_max)

def make_more_city():
    # build new rows ahead
    global enemy_chance
    target_row = player_row + rows_ahead
    new_rows = []
    for row in range(0, target_row + 1):
        if (row, 0) in buildings:
            continue # row already made
        new_rows.append(row)
        difficulty = min(rows_crossed / 100, 1.0) # 0 to 1, goes up over time
        tallest_allowed = min_height + (max_height - min_height) * (0.5 + 0.5 * difficulty)
        enemy_chance = 0.05 + 0.05 * difficulty
        for lane in range(num_lanes):
            height = random.uniform(min_height, tallest_allowed)
            buildings[row, lane] = height
    return new_rows

def start_jump_to(target_lane, target_row=None):
    # start a jump
    global jump_start_x, jump_start_y, jump_start_z
    global jump_target_x, jump_target_y, jump_target_z
    global jump_target_row, jump_target_lane, jump_progress, player_is_jumping
    if player_is_jumping:
        return # already jumping
    target_lane = max(0, min(num_lanes - 1, target_lane))
    if target_row is None:
        target_row = player_row + 1
    jump_start_x = player_x
    jump_start_y = player_y
    jump_start_z = player_z
    jump_target_x = lane_x(target_lane)
    jump_target_y = row_y(target_row)
    jump_target_z = buildings.get((target_row, target_lane), 0)
    jump_target_row = target_row
    jump_target_lane = target_lane
    jump_progress = 0.0
    player_is_jumping = True

def try_jump(direction):
    # handle w, a, d keys
    if direction == 'left':
        start_jump_to(player_lane - 1, target_row=player_row)
    elif direction == 'right':
        start_jump_to(player_lane + 1, target_row=player_row)
    else:
        start_jump_to(player_lane)

def update_movement():
    # move player each frame
    global jump_progress, player_x, player_y, player_z
    global player_row, player_lane, player_is_jumping, rows_crossed
    run_cheat_autopilot()
    if not player_is_jumping:
        return
    jump_progress += delta_time / jump_time
    if jump_progress >= 1.0:
        # jump done, land here
        jump_progress = 1.0
        player_x = jump_target_x
        player_y = jump_target_y
        player_z = jump_target_z
        player_row = jump_target_row
        player_lane = jump_target_lane
        player_is_jumping = False
        rows_crossed = player_row
        check_heart_pickup()
    else:
        # still in the air
        progress = jump_progress
        player_x = jump_start_x + (jump_target_x - jump_start_x) * progress
        player_y = jump_start_y + (jump_target_y - jump_start_y) * progress
        base_z = jump_start_z + (jump_target_z - jump_start_z) * progress
        hop = math.sin(progress * math.pi) * jump_hop_height
        player_z = base_z + hop

def draw_sky_and_ground():
    # draw sky and ground
    center_y = player_y
    half_width = 3000
    back_edge = center_y - 3000
    front_edge = center_y + 5000
    ceiling_height = 2500
    # ground
    glColor3f(0.22, 0.55, 0.22)
    glBegin(GL_QUADS)
    glVertex3f(-half_width, back_edge, -1)
    glVertex3f(half_width, back_edge, -1)
    glVertex3f(half_width, front_edge, -1)
    glVertex3f(-half_width, front_edge, -1)
    glEnd()
    # sky box, all sides
    glColor3f(0.55, 0.8, 0.98)
    glBegin(GL_QUADS)
    glVertex3f(-half_width, front_edge, -1)
    glVertex3f(half_width, front_edge, -1)
    glVertex3f(half_width, front_edge, ceiling_height)
    glVertex3f(-half_width, front_edge, ceiling_height)
    glVertex3f(-half_width, back_edge, -1)
    glVertex3f(half_width, back_edge, -1)
    glVertex3f(half_width, back_edge, ceiling_height)
    glVertex3f(-half_width, back_edge, ceiling_height)
    glVertex3f(-half_width, back_edge, -1)
    glVertex3f(-half_width, front_edge, -1)
    glVertex3f(-half_width, front_edge, ceiling_height)
    glVertex3f(-half_width, back_edge, ceiling_height)
    glVertex3f(half_width, back_edge, -1)
    glVertex3f(half_width, front_edge, -1)
    glVertex3f(half_width, front_edge, ceiling_height)
    glVertex3f(half_width, back_edge, ceiling_height)
    glVertex3f(-half_width, back_edge, ceiling_height)
    glVertex3f(half_width, back_edge, ceiling_height)
    glVertex3f(half_width, front_edge, ceiling_height)
    glVertex3f(-half_width, front_edge, ceiling_height)
    glEnd()

def estimate_viewer_position():
    # guess camera position
    px, py, pz = (player_x, player_y, player_z)
    if camera_mode == 0:
        angle = camera_angle
        viewer_x = px + camera_radius * math.sin(angle)
        viewer_y = py - camera_radius * math.cos(angle)
        viewer_z = pz + camera_height
    elif camera_mode == 1:
        viewer_x, viewer_y, viewer_z = (px, py, pz + player_leg_height + player_torso_height + 8)
    else:
        viewer_x, viewer_y, viewer_z = (px, py, pz + 700)
    return (viewer_x, viewer_y, viewer_z)

def draw_one_building(x, y, height, size, viewer_x, viewer_y, viewer_z):
    # draw one building
    base = 0.55
    half = size / 2
    left_shade = base * 0.55
    right_shade = min(1.0, base * 1.3)
    front_shade = base * 0.75
    back_shade = min(1.0, base * 1.05)
    if viewer_x < x - half:
        # left wall
        glColor3f(left_shade, left_shade, left_shade)
        glBegin(GL_QUADS)
        glVertex3f(x - half, y - half, 0)
        glVertex3f(x - half, y + half, 0)
        glVertex3f(x - half, y + half, height)
        glVertex3f(x - half, y - half, height)
        glEnd()
    if viewer_x > x + half:
        # right wall
        glColor3f(right_shade, right_shade, right_shade)
        glBegin(GL_QUADS)
        glVertex3f(x + half, y - half, 0)
        glVertex3f(x + half, y + half, 0)
        glVertex3f(x + half, y + half, height)
        glVertex3f(x + half, y - half, height)
        glEnd()
    if viewer_y < y - half:
        # front wall
        glColor3f(front_shade, front_shade, front_shade)
        glBegin(GL_QUADS)
        glVertex3f(x - half, y - half, 0)
        glVertex3f(x + half, y - half, 0)
        glVertex3f(x + half, y - half, height)
        glVertex3f(x - half, y - half, height)
        glEnd()
    if viewer_y > y + half:
        # back wall
        glColor3f(back_shade, back_shade, back_shade)
        glBegin(GL_QUADS)
        glVertex3f(x - half, y + half, 0)
        glVertex3f(x + half, y + half, 0)
        glVertex3f(x + half, y + half, height)
        glVertex3f(x - half, y + half, height)
        glEnd()
    if viewer_z > height:
        # roof
        glColor3f(base * 0.5, base * 0.5, base * 0.5)
        glBegin(GL_QUADS)
        glVertex3f(x - half, y - half, height)
        glVertex3f(x + half, y - half, height)
        glVertex3f(x + half, y + half, height)
        glVertex3f(x - half, y + half, height)
        glEnd()

def decor_building_height(row, side_index):
    # random height, for looks only
    own_random = random.Random(row * 10000 + side_index * 37 + 500000)
    return own_random.uniform(min_height * 0.6, max_height * 0.9)

def draw_heart(x, y, z):
    # draw pink diamond
    glColor3f(0.95, 0.25, 0.7)
    glPushMatrix()
    glTranslatef(x, y, z + 35)
    glRotatef(45, 0, 0, 1)
    glScalef(1.0, 1.0, 1.6)
    glutSolidCube(18)
    glPopMatrix()

def draw_city():
    # draw whole city
    draw_sky_and_ground()
    viewer_x, viewer_y, viewer_z = estimate_viewer_position()
    first_row = max(0, player_row - 2)
    last_row = player_row + rows_ahead
    decor_columns = 7 # extra buildings, for looks
    to_draw = []
    for row in range(first_row, last_row):
        for lane in range(num_lanes):
            height = buildings.get((row, lane))
            if height is None:
                continue
            to_draw.append((lane_x(lane), row_y(row), height))
        for side_index in range(1, decor_columns + 1):
            for direction in (-1, 1):
                if direction < 0:
                    x = lane_x(0) - side_index * lane_width
                else:
                    x = lane_x(num_lanes - 1) + side_index * lane_width
                height = decor_building_height(row, direction * side_index)
                to_draw.append((x, row_y(row), height))

    def squared_distance_from_viewer(building):
        # distance from camera
        x, y, height = building
        dx = x - viewer_x
        dy = y - viewer_y
        dz = height / 2 - viewer_z
        return dx * dx + dy * dy + dz * dz
    to_draw.sort(key=squared_distance_from_viewer, reverse=True) # far ones first
    for x, y, height in to_draw:
        draw_one_building(x, y, height, building_size, viewer_x, viewer_y, viewer_z)
    if heart_row is not None and first_row <= heart_row < last_row:
        x = lane_x(heart_lane)
        y = row_y(heart_row)
        z = buildings.get((heart_row, heart_lane), 0)
        draw_heart(x, y, z)

def draw_player():
    # draw spider-man
    leg_height = player_leg_height
    torso_height = player_torso_height
    head_radius = player_head_radius
    red = (0.75, 0.05, 0.05)
    blue = (0.05, 0.05, 0.7)
    dark = (0.1, 0.1, 0.1)
    glPushMatrix()
    glTranslatef(player_x, player_y, player_z)
    if game_over:
        glRotatef(90, 1, 0, 0) # falls down
    # legs
    glColor3f(*blue)
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * 10, 0, 0)
        gluCylinder(gluNewQuadric(), 7, 7, leg_height, 8, 4)
        glPopMatrix()
    lean_angle = 0
    if player_is_jumping:
        lean_angle = math.sin(jump_progress * math.pi) * 20
    glPushMatrix()
    glTranslatef(0, 0, leg_height)
    glRotatef(-lean_angle, 1, 0, 0)
    glColor3f(*red)
    if camera_mode != 1:
        # body, hidden in first person
        glPushMatrix()
        glTranslatef(0, 0, torso_height / 2)
        glScalef(1.1, 0.8, torso_height / 40)
        glutSolidCube(40)
        glPopMatrix()
    # shoulders
    glColor3f(*red)
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * player_shoulder_x, 0, player_shoulder_z)
        gluSphere(gluNewQuadric(), 8, 10, 10)
        glPopMatrix()
    # arms
    glColor3f(*blue)
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * player_shoulder_x, 0, player_shoulder_z)
        glRotatef(-90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), player_arm_radius, player_arm_radius - 1, player_arm_length, 8, 8)
        glPopMatrix()
    # hands
    glColor3f(*dark)
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * player_shoulder_x, player_arm_length, player_shoulder_z)
        gluSphere(gluNewQuadric(), player_hand_radius, 8, 8)
        glPopMatrix()
    if camera_mode != 1:
        # belt, head, eyes
        glColor3f(*dark)
        glPushMatrix()
        glTranslatef(0, 0, 2)
        glScalef(1.15, 0.85, 0.15)
        glutSolidCube(40)
        glPopMatrix()
        glColor3f(*red)
        glPushMatrix()
        glTranslatef(0, 0, torso_height + head_radius)
        gluSphere(gluNewQuadric(), head_radius, 10, 10)
        glPopMatrix()
        glColor3f(0.95, 0.95, 0.95)
        for side in (-1, 1):
            glPushMatrix()
            glTranslatef(side * 6, 10, torso_height + head_radius + 2)
            glScalef(1.4, 0.4, 1.0)
            glutSolidCube(6)
            glPopMatrix()
    glPopMatrix()
    glPopMatrix()
################################################################################
# combat_rescue
################################################################################
def toggle_cheat_mode():
    # turn cheat on or off
    global cheat_mode, cheat_timer
    cheat_mode = not cheat_mode
    cheat_timer = 0.0

def pick_cheat_target_lane():
    # pick lane for cheat
    if victim_row is not None:
        return victim_lane
    return player_lane

def cheat_should_fire():
    # check enemy ahead
    lane_center_x = lane_x(player_lane)
    for e in enemies.values():
        if e['y'] > player_y and abs(e['x'] - lane_center_x) < 40:
            return True
    return False

def run_cheat_autopilot():
    # auto play the game
    global cheat_timer
    if not (cheat_mode and camera_mode == 1):
        return
    if cheat_should_fire():
        fire_web()
    if not player_is_jumping:
        cheat_timer += delta_time
        if cheat_timer >= cheat_jump_gap:
            cheat_timer = 0.0
            start_jump_to(pick_cheat_target_lane())

def update_cheat_look():
    # look at nearest enemy
    global camera_look_angle
    target_angle = 0.0
    if cheat_mode and camera_mode == 1:
        nearest_dist = None
        nearest_dx = 0.0
        nearest_dy = 1.0
        for e in enemies.values():
            dx = e['x'] - player_x
            dy = e['y'] - player_y
            dist = math.hypot(dx, dy)
            if nearest_dist is None or dist < nearest_dist:
                nearest_dist = dist
                nearest_dx = dx
                nearest_dy = dy
        if nearest_dist is not None:
            target_angle = math.atan2(nearest_dx, nearest_dy)
    diff = (target_angle - camera_look_angle + math.pi) % (2 * math.pi) - math.pi
    max_step = camera_look_turn_speed * delta_time
    if diff > max_step:
        diff = max_step
    elif diff < -max_step:
        diff = -max_step
    camera_look_angle += diff

def setup_new_row(row):
    # add enemies to row
    if row <= 2:
        return # keep start safe
    for lane in range(num_lanes):
        if random.random() < enemy_chance:
            x = lane_x(lane)
            y = row_y(row)
            z = buildings.get((row, lane), 0) + 30
            enemies[row, lane] = {'x': x, 'y': y, 'z': z}

def check_and_place_victim():
    # add victim if it's time
    global victim_row, victim_lane, victim_start_row
    if victim_row is None and (next_victim_row, 0) in buildings:
        v_lane = random.randint(0, num_lanes - 1)
        victim_row = next_victim_row
        victim_lane = v_lane
        victim_start_row = rows_crossed
        enemies.pop((next_victim_row, v_lane), None)

def move_enemies():
    # move enemies to player
    for e in enemies.values():
        if e['y'] <= player_y:
            continue
        dx = player_x - e['x']
        dy = player_y - e['y']
        dist = math.hypot(dx, dy)
        if dist > 1:
            e['x'] += enemy_speed * delta_time * dx / dist
            e['y'] += enemy_speed * delta_time * dy / dist

def fire_web():
    # shoot a web
    global web_cooldown
    if web_cooldown > 0:
        return
    webs.append([player_lane, player_y, True])
    web_cooldown = web_cooldown_time

def update_webs():
    # move webs, check hits
    global web_cooldown, kill_streak, score_multiplier, kill_score
    web_cooldown = max(0.0, web_cooldown - delta_time)
    webs_still_going = []
    for web in webs:
        lane, y, alive = web
        y += web_speed * delta_time
        web[1] = y
        web_x = lane_x(lane)
        hit_key = None
        for key, e in enemies.items():
            dx = e['x'] - web_x
            dy = e['y'] - y
            if math.hypot(dx, dy) < enemy_hit_range:
                hit_key = key
                break
        if hit_key is not None:
            # hit, add points
            del enemies[hit_key]
            kill_streak += 1
            score_multiplier = min(max_multiplier, 1 + kill_streak // streak_per_multiplier)
            kill_score += kill_base_points * score_multiplier
            continue
        if round(y / row_spacing) > player_row + rows_ahead:
            continue # gone too far
        webs_still_going.append(web)
    webs[:] = webs_still_going

def check_landing():
    # check hit, save, or miss
    global player_lives, kill_streak, score_multiplier, rescue_score
    global victim_row, victim_lane, next_victim_row, victim_start_row, failed_rescues
    if player_is_jumping:
        return
    hit_key = None
    for key, e in enemies.items():
        dx = e['x'] - player_x
        dy = e['y'] - player_y
        if math.hypot(dx, dy) < player_hit_range:
            hit_key = key
            break
    if hit_key is not None:
        # enemy got player
        del enemies[hit_key]
        player_lives -= 1
        kill_streak = 0
        score_multiplier = 1
    here = (player_row, player_lane)
    if victim_row is not None and here == (victim_row, victim_lane):
        # victim saved
        rows_used = rows_crossed - victim_start_row
        rows_left = max(0, rescue_window - rows_used)
        speed_bonus = int(rescue_base_points * (rows_left / rescue_window))
        rescue_score += (rescue_base_points + speed_bonus) * score_multiplier
        victim_row = None
        victim_lane = None
        next_victim_row = rows_crossed + random.randint(victim_gap_min, victim_gap_max)
        victim_start_row = None
    if victim_row is not None and victim_start_row is not None:
        rows_since_victim_appeared = rows_crossed - victim_start_row
        if rows_since_victim_appeared > rescue_window:
            # too slow, victim lost
            failed_rescues += 1
            victim_row = None
            victim_lane = None
            next_victim_row = rows_crossed + random.randint(victim_gap_min, victim_gap_max)
            victim_start_row = None
            kill_streak = 0
            score_multiplier = 1

def draw_enemies():
    # draw all enemies
    for e in enemies.values():
        glPushMatrix()
        glTranslatef(e['x'], e['y'], e['z'])
        glColor3f(1, 0, 0)
        gluSphere(gluNewQuadric(), 20, 10, 10)
        glColor3f(0, 0, 0)
        glTranslatef(8, -8, 8)
        gluSphere(gluNewQuadric(), 9, 8, 8)
        glPopMatrix()

def draw_webs():
    # draw all webs
    glColor3f(1, 1, 1)
    for lane, y, alive in webs:
        x = lane_x(lane)
        nearest_row = round(y / row_spacing)
        z = buildings.get((nearest_row, lane), 100) + 40
        glPushMatrix()
        glTranslatef(x, y, z)
        glutSolidCube(10)
        glPopMatrix()

def draw_victim():
    # draw the victim
    if victim_row is None:
        return
    x = lane_x(victim_lane)
    y = row_y(victim_row)
    z = buildings.get((victim_row, victim_lane), 0)
    glPushMatrix()
    glTranslatef(x, y, z)
    glColor3f(0.85, 0.7, 0.55)
    glPushMatrix()
    glTranslatef(0, 0, 15)
    glScalef(1, 0.7, 1.3)
    glutSolidCube(30)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 43)
    gluSphere(gluNewQuadric(), 11, 10, 10)
    glPopMatrix()
    glPopMatrix()
################################################################################
# camera_state
################################################################################
def reset_camera():
    # reset camera to start
    global camera_mode, camera_angle, camera_height, camera_radius
    global camera_shake, smooth_x, smooth_y, smooth_z
    camera_mode = 0
    camera_angle = 0.0
    camera_height = 300.0
    camera_radius = 350.0
    camera_shake = 0.0
    smooth_x = None
    smooth_y = None
    smooth_z = None

def toggle_camera_mode():
    # change camera view
    global camera_mode
    camera_mode = (camera_mode + 1) % 3

def handle_special_keys(key):
    # arrow keys move camera
    global camera_angle, camera_height
    if key == GLUT_KEY_LEFT:
        camera_angle -= 0.05
    elif key == GLUT_KEY_RIGHT:
        camera_angle += 0.05
    elif key == GLUT_KEY_UP:
        camera_height = min(1500.0, camera_height + 15.0)
    elif key == GLUT_KEY_DOWN:
        camera_height = max(50.0, camera_height - 15.0)

def follow_camera():
    # camera follows player, smooth
    global smooth_x, smooth_y, smooth_z
    target_x = player_x
    target_y = player_y
    target_z = player_z
    if smooth_x is None:
        smooth_x = target_x
        smooth_y = target_y
        smooth_z = target_z
    else:
        smooth_x += (target_x - smooth_x) * 0.12
        smooth_y += (target_y - smooth_y) * 0.12
        smooth_z += (target_z - smooth_z) * 0.12
    return (smooth_x, smooth_y, smooth_z)

def zoom_camera(amount):
    # move camera closer or far
    global camera_radius
    camera_radius = max(150.0, min(800.0, camera_radius + amount))

def trigger_camera_shake(amount=12.0):
    # start camera shake
    global camera_shake
    camera_shake = max(camera_shake, amount)

def update_camera_effects():
    # shake fades over time
    global camera_shake
    if camera_shake > 0.0:
        camera_shake -= 0.8
        if camera_shake < 0.0:
            camera_shake = 0.0

def setup_camera():
    # set camera for this frame
    px, py, pz = follow_camera()
    shake_x = 0.0
    shake_y = 0.0
    shake_z = 0.0
    if camera_shake > 0.0:
        shake_x = math.sin(camera_shake * 2.0) * camera_shake * 0.15
        shake_y = math.cos(camera_shake * 2.0) * camera_shake * 0.15
        shake_z = math.sin(camera_shake * 3.0) * camera_shake * 0.08
    px += shake_x
    py += shake_y
    pz += shake_z
    aspect_ratio = window_width / window_height if window_height > 0 else 1.25
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    current_fov = 90.0
    if camera_mode == 1 and player_is_jumping:
        current_fov = 96.0
    gluPerspective(current_fov, aspect_ratio, 0.1, 8000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    if camera_mode == 1:
        # first person
        eye_x = px
        eye_y = py
        eye_z = pz + player_leg_height + player_torso_height + 8
        center_x = eye_x + 100.0 * math.sin(camera_look_angle)
        center_y = eye_y + 100.0 * math.cos(camera_look_angle)
        center_z = eye_z
        up_x, up_y, up_z = (0, 0, 1)
    elif camera_mode == 0:
        # third person
        eye_x = px + camera_radius * math.sin(camera_angle)
        eye_y = py - camera_radius * math.cos(camera_angle)
        eye_z = pz + camera_height
        center_x = px
        center_y = py
        center_z = pz + 20.0
        up_x, up_y, up_z = (0, 0, 1)
    else:
        # top down
        eye_x = px
        eye_y = py
        eye_z = pz + 600.0
        center_x = px
        center_y = py
        center_z = pz
        up_x, up_y, up_z = (0, 1, 0)
    gluLookAt(eye_x, eye_y, eye_z, center_x, center_y, center_z, up_x, up_y, up_z)

def render_hub():
    # draw score and lives text
    total_score = kill_score + rescue_score
    lives = player_lives
    max_lives_local = max_lives
    failed = failed_rescues
    max_failed = max_failed_rescues
    mode_names = {0: 'Third-Person(TPV)', 1: 'First-Person(FPV)', 2: 'Top-Down'}
    current_mode_str = mode_names.get(camera_mode, 'Third-Person')
    h = window_height
    w = window_width
    draw_text(10, h - 55, f'Player Lives:{lives}/{max_lives_local}')
    draw_text(10, h - 80, f'Game Score: {total_score}')
    draw_text(10, h - 105, f'Failed Rescues:{failed}/{max_failed}')
    draw_text(10, h - 130, f'Camera Mode:{current_mode_str}[Right Click to Toggle]')
    cx = w / 2.0
    cy = h / 2.0
    if game_over:
        draw_text(cx - 90, cy + 50, ' ===GAME OVER===')
        if lives <= 0:
            draw_text(cx - 120, cy + 20, 'Reason: You ran out of lives!')
        elif failed >= max_failed:
            draw_text(cx - 130, cy + 20, 'Reason: Too many failed rescues ')
        draw_text(cx - 75, cy - 20, f'Final Score: {total_score}')
        draw_text(cx - 120, cy - 60, "Press 'R' Key to Restart Game")

def check_game_conditions():
    # check if game is lost
    global game_over
    lives = player_lives
    failed = failed_rescues
    max_failed = max_failed_rescues
    if game_over:
        return
    if lives <= 0 or failed >= max_failed:
        game_over = True

def check_game_over():
    # update shake, check end
    update_camera_effects()
    check_game_conditions()

def draw_info():
    # draw all text
    render_hub()

def change_camera_mode():
    # right click calls this
    toggle_camera_mode()

def adjust_camera(key):
    # arrow key calls this
    handle_special_keys(key)
################################################################################
# main
################################################################################
def grow_city():
    # build city, add things
    new_rows = make_more_city()
    for row in new_rows:
        setup_new_row(row)
    check_and_place_victim()
    check_and_place_heart()

def restart_game():
    # reset for new game
    global player_row, player_lane, player_x, player_y, player_z
    global player_is_jumping, jump_progress
    global buildings, enemies, webs, web_cooldown
    global victim_row, victim_lane, next_victim_row, victim_start_row
    global failed_rescues, kill_score, kill_streak, rescue_score, rows_crossed
    global player_lives, game_over
    global score_multiplier, camera_look_angle
    global heart_row, heart_lane, next_heart_row
    player_row = 0
    player_lane = num_lanes // 2
    player_x = lane_x(player_lane)
    player_y = row_y(player_row)
    player_is_jumping = False
    jump_progress = 0.0
    buildings = {}
    enemies = {}
    webs = []
    web_cooldown = 0.0
    victim_row = None
    victim_lane = None
    next_victim_row = random.randint(victim_gap_min, victim_gap_max)
    victim_start_row = None
    failed_rescues = 0
    kill_score = 0
    kill_streak = 0
    score_multiplier = 1
    rescue_score = 0
    rows_crossed = 0
    player_lives = max_lives
    game_over = False
    camera_look_angle = 0.0
    heart_row = None
    heart_lane = None
    next_heart_row = random.randint(heart_gap_min, heart_gap_max)
    reset_camera()
    grow_city()
    player_z = buildings.get((player_row, player_lane), 0.0)
    print('Starting Over')

def keyboard_listener(key, x, y):
    # normal key pressed
    if key == b'r':
        restart_game()
        glutPostRedisplay()
        return
    if game_over:
        glutPostRedisplay()
        return
    if key == b'w':
        try_jump('forward')
    elif key == b'a':
        try_jump('left')
    elif key == b'd':
        try_jump('right')
    elif key == b'c':
        toggle_cheat_mode()
    glutPostRedisplay()

def special_key_listener(key, x, y):
    # arrow key pressed
    adjust_camera(key)
    glutPostRedisplay()

def mouse_listener(button, state, x, y):
    # mouse button pressed
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN and (not game_over):
        fire_web()
    if button == GLUT_RIGHT_BUTTON and state == GLUT_DOWN:
        change_camera_mode()
    glutPostRedisplay()

def update_delta_time():
    # time since last frame
    global last_time, delta_time
    now = time.time()
    delta_time = now - last_time
    last_time = now

def idle():
    # runs every frame
    update_delta_time()
    if not game_over:
        update_movement()
        grow_city()
        move_enemies()
        update_webs()
        check_landing()
        check_game_over()
    update_cheat_look()
    follow_camera()
    glutPostRedisplay()

def show_screen():
    # draw everything
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, window_width, window_height)
    setup_camera()
    draw_city()
    draw_player()
    draw_enemies()
    draw_webs()
    draw_victim()
    draw_info()
    glutSwapBuffers()

def main():
    # start the game
    global last_time
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(window_width, window_height)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b'Spiderman City')
    glutDisplayFunc(show_screen)
    glutKeyboardFunc(keyboard_listener)
    glutSpecialFunc(special_key_listener)
    glutMouseFunc(mouse_listener)
    glutIdleFunc(idle)
    restart_game()
    last_time = time.time()
    glutMainLoop()
if __name__ == '__main__':
    main()