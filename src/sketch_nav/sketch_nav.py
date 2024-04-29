import time
import pygame
import math
import logging

import bosdyn.client
import bosdyn.client.util
from bosdyn.api import basic_command_pb2
from bosdyn.api import geometry_pb2 as geo
from bosdyn.api.basic_command_pb2 import RobotCommandFeedbackStatus
from bosdyn.client import math_helpers
from bosdyn.client.frame_helpers import (BODY_FRAME_NAME, ODOM_FRAME_NAME, VISION_FRAME_NAME,
                                         get_se2_a_tform_b)
from bosdyn.client.lease import LeaseClient, LeaseKeepAlive
from bosdyn.client.robot_command import (RobotCommandBuilder, RobotCommandClient,
                                         block_for_trajectory_cmd, blocking_stand)
from bosdyn.client.robot_state import RobotStateClient

logger = logging.getLogger(__name__)


WIDTH_PX, HEIGHT_PX = 700, 800 # Width and height of the pygame
WIDTH_M, HEIGHT_M = 4.27, 4.88 # Width and height of the maze in real life

BLACK = (0, 0, 0)
RED = (255, 0, 0)

waypoints = []
moves = []


def init_interface():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH_PX, HEIGHT_PX))
    pygame.display.set_caption("Sketch Nav")
    background_image = pygame.image.load('maze.png')
    background_image = pygame.transform.scale(background_image, (WIDTH_PX, HEIGHT_PX))
    drawing_surface = pygame.Surface((WIDTH_PX, HEIGHT_PX))
    drawing_surface.set_colorkey(BLACK)
    drawing_surface.set_alpha(128)

    waypoints.append((100, 700))

    pygame.draw.circle(drawing_surface, RED, waypoints[0], 10)
    return screen, background_image, drawing_surface


def handle_events(drawing_surface):
    global drawing, last_pos, path
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
        elif event.type == pygame.MOUSEBUTTONUP:
            # Add a new waypoint when the user clicks a point on the maze
            print('Adding a new waypoint: ' + str(event.pos))
            waypoints.append(event.pos)
            pygame.draw.circle(drawing_surface, RED, event.pos, 7)
            pygame.draw.line(drawing_surface, RED, waypoints[-1], waypoints[-2], 5)


def points_to_moves(points):
    # Ratio between pixel values and real world positions
    x_px_to_m = WIDTH_M / WIDTH_PX
    y_px_to_m = HEIGHT_M / HEIGHT_PX

    global moves
    headings = []

    i = 1
    for i in range(len(points)-1):
        cp = points[i]
        np = points[i+1]

        dx = np[0] - cp[0]
        dy = np[1] - cp[1]

        headings.append(math.degrees(math.atan2(dx, dy)))

        #if i != 0:
        rel_heading = headings[i]-headings[i-1]
        if rel_heading > 180:
            rel_heading -= 360
        if rel_heading < -180:
            rel_heading += 360

        mx = math.sqrt((dy * y_px_to_m)**2 + (dx * x_px_to_m)**2)
        moves.append((0, 0, rel_heading))
        moves.append((mx, 0, 0))
        
       #else:
        #    moves.append((0, 0, 90-math.degrees(math.atan2(dx, dy))))


def relative_move(dx, dy, dyaw, frame_name, robot_command_client, robot_state_client, stairs=False):
    transforms = robot_state_client.get_robot_state().kinematic_state.transforms_snapshot

    # Build the transform for where we want the robot to be relative to where the body currently is.
    body_tform_goal = math_helpers.SE2Pose(x=dx, y=dy, angle=dyaw)
    # We do not want to command this goal in body frame because the body will move, thus shifting
    # our goal. Instead, we transform this offset to get the goal position in the output frame
    # (which will be either odom or vision).
    out_tform_body = get_se2_a_tform_b(transforms, frame_name, BODY_FRAME_NAME)
    out_tform_goal = out_tform_body * body_tform_goal

    # Command the robot to go to the goal point in the specified frame. The command will stop at the
    # new position.
    robot_cmd = RobotCommandBuilder.synchro_se2_trajectory_point_command(
        goal_x=out_tform_goal.x, goal_y=out_tform_goal.y, goal_heading=out_tform_goal.angle,
        frame_name=frame_name, params=RobotCommandBuilder.mobility_params(stair_hint=stairs))
    end_time = 10.0
    cmd_id = robot_command_client.robot_command(lease=None, command=robot_cmd,
                                                end_time_secs=time.time() + end_time)
    # Wait until the robot has reached the goal.
    while True:
        feedback = robot_command_client.robot_command_feedback(cmd_id)
        mobility_feedback = feedback.feedback.synchronized_feedback.mobility_command_feedback
        if mobility_feedback.status != RobotCommandFeedbackStatus.STATUS_PROCESSING:
            print('Failed to reach the goal')
            return False
        traj_feedback = mobility_feedback.se2_trajectory_feedback
        if (traj_feedback.status == traj_feedback.STATUS_AT_GOAL and
                traj_feedback.body_movement_status == traj_feedback.BODY_STATUS_SETTLED):
            print('Arrived at the goal.')
            return True
        # time.sleep(0)


def main():
    # Initialize robot
    import argparse
    parser = argparse.ArgumentParser()
    bosdyn.client.util.add_base_arguments(parser)

    print("Getting options") 
    parser.add_argument('--frame', choices=[VISION_FRAME_NAME, ODOM_FRAME_NAME],
                        default=ODOM_FRAME_NAME, help='Send the command in this frame.')
    options = parser.parse_args()

    bosdyn.client.util.setup_logging(options.verbose)

    # Create robot object.
    sdk = bosdyn.client.create_standard_sdk('RobotCommandMaster')
    robot = sdk.create_robot(options.hostname)
    bosdyn.client.util.authenticate(robot)

    ##### Start moving the robot #####

    # Check that an estop is connected with the robot so that the robot commands can be executed.
    assert not robot.is_estopped(), 'Robot is estopped. Please use an external E-Stop client, ' \
                                    'such as the estop SDK example, to configure E-Stop.'

    # Create the lease client.
    lease_client = robot.ensure_client(LeaseClient.default_service_name)

    # Setup clients for the robot state and robot command services.
    robot_state_client = robot.ensure_client(RobotStateClient.default_service_name)
    robot_command_client = robot.ensure_client(RobotCommandClient.default_service_name)

    with LeaseKeepAlive(lease_client, must_acquire=True, return_at_exit=True):
        # Power on the robot and stand it up.
        robot.time_sync.wait_for_sync()
        print('Powering on the robot')
        robot.power_on()

        print('The robot is standing')
        blocking_stand(robot_command_client)
        
        # Initialize interface
        screen, background_image, drawing_surface = init_interface()

        running = True
        while running:
            screen.blit(background_image, (0, 0))
            screen.blit(drawing_surface, (0, 0))
            handle_events(drawing_surface)

            # This is a hacky way to stop the interface
            try:
                pygame.display.flip()
            except:
                running = False

        points_to_moves(waypoints)        

        # Call relative move function here to move the robots
        for move in moves:
            print('Moving: (dx=' + str(move[0]) + ', dy=' + str(move[1]) + ', dyaw=' + str(move[2]))
            relative_move(move[0], move[1], math.radians(move[2]), options.frame, robot_command_client, robot_state_client, stairs=False)
            

        print('Completed the movement!')

if __name__ == "__main__":
    main()