import pygame
import math

WIDTH_PX, HEIGHT_PX = 1000, 1000
WIDTH_M, HEIGHT_M = 10, 10

BLACK = (0, 0, 0)
RED = (255, 0, 0)

waypoints = []
moves = []

def init_interface():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH_PX, HEIGHT_PX))
    pygame.display.set_caption("Sketch Nav")
    background_image = pygame.image.load('src/test.jpg')
    background_image = pygame.transform.scale(background_image, (WIDTH_PX, HEIGHT_PX))
    drawing_surface = pygame.Surface((WIDTH_PX, HEIGHT_PX))
    drawing_surface.set_colorkey(BLACK)
    drawing_surface.set_alpha(128)

    waypoints.append((220, 650))

    pygame.draw.circle(drawing_surface, RED, waypoints[0], 10)
    return screen, background_image, drawing_surface


def handle_events(drawing_surface):
    global drawing, last_pos, path
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
        elif event.type == pygame.MOUSEBUTTONUP:
            # Add a new waypoint when the user clicks a point on the maze
            waypoints.append(event.pos)
            pygame.draw.circle(drawing_surface, RED, event.pos, 7)
            pygame.draw.line(drawing_surface, RED, waypoints[-1], waypoints[-2], 5)


def points_to_moves(points):
    # Ratio between pixel values and real world positions

    x_px_to_m = WIDTH_M / WIDTH_PX
    y_px_to_m = HEIGHT_M / HEIGHT_PX

    i = 0
    heading = 0
    for i in range(len(points)-1):
        cp = points[i]
        np = points[i+1]

        dx = np[0] - cp[0]
        dy = np[1] - cp[1]

        

        theta = -(math.degrees(math.atan2(dy, dx)) - heading)
        print("heading = " + str(heading))
        # print("raw theta = " + str(-math.degrees(math.atan2(dy, dx))))
        # print("computed turn = " + str(theta))
        heading += theta
        # if len(moves) is not 0:
        #     theta = theta - moves[i-2][2]

        moves.append((0, 0, theta))
        # print("adding a turn: " + str(-theta))

        mx = math.sqrt((dy * y_px_to_m)**2 + (dx * x_px_to_m)**2)

        moves.append((mx, 0, 0))
        # print("adding a move: " + str(mx))


def main():
    screen, background_image, drawing_surface = init_interface()

    running = True
    while running:
        screen.blit(background_image, (0, 0))
        screen.blit(drawing_surface, (0, 0))
        handle_events(drawing_surface)

        try:
            pygame.display.flip()
        except:
            running = False

    points_to_moves(waypoints)

    for move in moves:
        print(move)


if __name__ == "__main__":
    main()