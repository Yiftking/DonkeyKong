# environment.py - Manages game rules, collisions, and state
import pygame
import random
import torch
import numpy as np # Added for distance calculations
from platform_class import Platform
from donkey_kong import DonkeyKong
from barrel import Barrel
from princess import Princess
from ladder import Ladder

class Environment:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Game state variables
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.barrel_timer = 0
        self.barrel_interval = 10  # Randomize next barrel interval
        self.barrel_count = 0
        
        # Gravity and physics constants
        self.gravity = 0.8
        
        # Sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.platforms = pygame.sprite.Group()
        self.ladders = pygame.sprite.Group()
        self.barrels = pygame.sprite.Group()
        
        # Player reference (will be set later)
        self.player = None
        
        # Step tracking for RL
        self.steps = 0
        self.reached_princess = False
        
        # Create game elements
        self._create_platforms()
        self._create_ladders()
        self._create_donkey_kong()
        self._create_princess()
    
    def _create_platforms(self):
        # Create angled platforms like original Donkey Kong
        # Platforms are angled downward from left to right
        platform_list = [
            # width, height, x, y, angle
            [self.screen_width, 20, 0, self.screen_height - 20, 0],           # Ground (flat)
            [800, 20, 400, self.screen_height - 160, -8],                     # First platform (angled)
            [900, 20, 250, self.screen_height - 300, 8],                      # Second platform (angled opposite)
            [950, 20, 300, self.screen_height - 440, -8],                     # Third platform (angled)
            [900, 20, 250, self.screen_height - 580, 8],                      # Fourth platform (angled opposite)
            [600, 20, 400, self.screen_height - 720, 0],                      # Top platform (flat)
        ]
        
        for index, platform_data in enumerate(platform_list):
            p = Platform(platform_data[0], platform_data[1], platform_data[2], platform_data[3])
            p.platform_number = index  # assign a number to each platform
            if len(platform_data) > 4:
                p.angle = platform_data[4]
            self.platforms.add(p)
            self.all_sprites.add(p)

    
    def _create_ladders(self):
        # Create ladders that connect between platforms
        # Adjusted for angled platforms
        ladder_list = [
            # x, bottom_y, height
            [500, self.screen_height - 20, 120],      # Ground to first platform
            [1000, self.screen_height - 160, 120],    # First to second platform (right side)
            [300, self.screen_height - 300, 120],     # Second to third platform (left side)
            [950, self.screen_height - 440, 120],     # Third to fourth platform (right side)
            [400, self.screen_height - 580, 120],     # Fourth to top platform (left side)
        ]
        
        # CHANGED: Added enumerate to assign platform numbers to ladders
        for index, ladder_info in enumerate(ladder_list):
            ladder = Ladder(ladder_info[0], ladder_info[1], ladder_info[2])
            ladder.platform_number = index  # Associate ladder with the platform it starts from
            self.ladders.add(ladder)
            self.all_sprites.add(ladder)
    
    def _create_donkey_kong(self):
        # Create Donkey Kong at the top
        self.donkey_kong = DonkeyKong(500, self.screen_height - 780)
        self.all_sprites.add(self.donkey_kong)
    
    def _create_princess(self):
        # Create Princess at the top
        self.princess = Princess(700, self.screen_height - 770)
        self.all_sprites.add(self.princess)
    
    def add_player(self, player):
        # Add player to environment
        self.player = player
        player.environment = self
        self.all_sprites.add(player)
    
    def _throw_barrel(self):
        # Spawn barrel from Donkey Kong's left side (slightly inset vertically)
        barrel = Barrel(0, 0)
        barrel.rect.x = self.donkey_kong.rect.left - barrel.rect.width - 2
        barrel.rect.y = self.donkey_kong.rect.top + 8
        barrel.change_x = -2  # Start moving left out of DK's left side (slower)
        self.barrels.add(barrel)
        self.all_sprites.add(barrel)

    def update(self):
        if self.game_over:
            return

        # Update all sprites except player
        for sprite in self.all_sprites:
            if sprite != self.player:
                sprite.update()

        # Throw barrels (timer)
        self.barrel_timer += 1
        random_chance = random.random()
        if self.barrel_timer >= self.barrel_interval:
            self._throw_barrel()
            self.barrel_timer = 0
            self.barrel_interval = random.randint(100, 300)  # Randomize next barrel interval

        # ===== Barrel Physics =====
        for barrel in list(self.barrels):
            # If barrel is currently rolling on a platform, keep it on that platform
            if getattr(barrel, 'on_platform', False) and getattr(barrel, 'current_platform', None):
                platform = barrel.current_platform
                # Keep barrel stuck to platform top and move horizontally
                barrel.change_y = 0
                barrel.rect.bottom = platform.rect.top
                barrel.rect.x += barrel.change_x

                # Edge detection: when reaching edge, start falling
                edge_threshold = 10
                if barrel.change_x < 0 and barrel.rect.right <= platform.rect.left + edge_threshold:
                    barrel.on_platform = False
                    barrel.current_platform = None
                    barrel.change_y = 1
                    barrel.rect.x -= 1
                elif barrel.change_x > 0 and barrel.rect.left >= platform.rect.right - edge_threshold:
                    barrel.on_platform = False
                    barrel.current_platform = None
                    barrel.change_y = 1
                    barrel.rect.x += 1

            else:
                # Track previous vertical position to detect crossing a platform between frames
                prev_bottom = barrel.rect.bottom

                # Apply gravity
                barrel.change_y += self.gravity

                # Move barrel
                barrel.rect.y += barrel.change_y
                barrel.rect.x += barrel.change_x

                # Check platform collision using crossing test to avoid skipping
                for platform in self.platforms:
                    new_bottom = barrel.rect.bottom

                    # Horizontal overlap check
                    horizontally_overlapping = (barrel.rect.right > platform.rect.left and
                                                barrel.rect.left < platform.rect.right)

                    # Check if barrel crossed the platform top between previous and current frame
                    if (prev_bottom <= platform.rect.top and
                        new_bottom >= platform.rect.top and
                        barrel.change_y >= 0 and
                        horizontally_overlapping):

                        # Land on the platform and start rolling
                        barrel.rect.bottom = platform.rect.top
                        barrel.change_y = 0
                        barrel.on_platform = True
                        barrel.current_platform = platform

                        # Decide horizontal roll direction after landing.
                        # Prefer platform.angle if provided; otherwise roll toward nearest edge.
                        speed = 2
                        plat_angle = getattr(platform, 'angle', 0)
                        if plat_angle:
                            barrel.change_x = speed if plat_angle > 0 else -speed
                        else:
                            plat_center = (platform.rect.left + platform.rect.right) / 2
                            barrel.change_x = -speed if barrel.rect.centerx < plat_center else speed

                        break

            # Remove barrel if it falls off screen or reaches bottom left
            if barrel.rect.top > self.screen_height or (barrel.rect.bottom >= self.screen_height - 40 and barrel.rect.right < 50):
                barrel.kill()

        # ===== Player Physics =====
        if self.player:
            # Synchronize player's on_ladder state with environment detection
            #self.player.on_ladder = self.is_player_on_ladder()

            # Apply gravity if not on ladder
            if not self.player.on_ladder:
                self.player.change_y += self.gravity
                # Cap falling speed
                if self.player.change_y > 12:
                    self.player.change_y = 12
            else:
                # On ladder - no gravity, allow player input to control vertical movement
                pass

            # Move player
            # Track previous vertical position to detect upward collisions
            prev_top = self.player.rect.top

            self.player.rect.x += self.player.change_x
            self.player.rect.y += self.player.change_y

            # Handle head collisions when moving upward (prevent passing through platforms)
            if self.player.change_y < 0 and not self.player.on_ladder:
                for platform in self.platforms:
                    # Horizontal overlap check using player's center
                    if platform.rect.left <= self.player.rect.centerx <= platform.rect.right:
                        # If player's top crossed into the platform from below, stop upward movement
                        if prev_top >= platform.rect.bottom and self.player.rect.top <= platform.rect.bottom:
                            self.player.rect.top = platform.rect.bottom
                            self.player.change_y = 0
                            break

            # Keep player on screen horizontally
            if self.player.rect.left < 0:
                self.player.rect.left = 0
            if self.player.rect.right > self.screen_width:
                self.player.rect.right = self.screen_width

            # Platform collision for player (only if not on ladder)
            if not self.player.on_ladder:
                for platform in self.platforms:
                    if (self.player.rect.bottom >= platform.rect.top - 2 and 
                        self.player.rect.top < platform.rect.top and
                        self.player.change_y > 0 and
                        platform.rect.left <= self.player.rect.centerx <= platform.rect.right):
                        
                        self.player.rect.bottom = platform.rect.top
                        self.player.change_y = 0
                        self.player.is_jumping = False
                        break

            # Prevent falling through bottom of screen
            if self.player.rect.bottom > self.screen_height:
                self.player.rect.bottom = self.screen_height
                self.player.change_y = 0
                self.player.is_jumping = False

            # Barrel collision
            if pygame.sprite.spritecollide(self.player, self.barrels, True):
                self.lives -= 1
                self.player.rect.x = 50
                self.player.rect.y = self.screen_height - 60
                self.player.on_ladder = False
                self.player.change_y = 0
                self.player.is_jumping = False

                if self.lives <= 0:
                    self.game_over = True

            # Princess collision (win condition)
            if pygame.sprite.collide_rect(self.player, self.princess):
                self.score += 1000
                self.player.rect.x = 50
                self.player.rect.y = self.screen_height - 60
                self.player.on_ladder = False
                self.player.change_y = 0
                for barrel in self.barrels:
                    barrel.kill()
                self.reached_princess = True  # <-- חשוב: מסמן ניצחון

            # Ensure player sprite updates (animation/image switching)
            try:
                self.player.update()
            except Exception:
                pass

    def get_state(self):
        # ... (נשאר זהה, לא משתנה) ...
        state = {
            'player_platform': -1,
            'player_x': 0,
            'height_from_platform': 0,
            'on_ladder': 0,
            'in_air': 0,
            'ladder_dx': 0,
            'barrel_dx': 9999,
            'princess_dx': 0,
            'same_platform_princess': 0,
            'platform_left_dx': 0,
            'platform_right_dx': 0
        }

        if not self.player:
            return state

        player_x = self.player.rect.centerx
        state['player_x'] = player_x

        # Add player's vertical position to the state
        state['player_y'] = self.player.rect.centery

        # --- Detect platform player is on or above ---
        current_platform = None
        self.player.current_platform_number = -1  # default if not on any platform

        # Standing on platform
        for p in self.platforms:
            if (p.rect.left <= player_x <= p.rect.right and
                abs(self.player.rect.bottom - p.rect.top) < 12):
                current_platform = p
                state['player_platform'] = p.platform_number
                self.player.current_platform_number = p.platform_number  # <-- track player platform
                state['height_from_platform'] = 0
                break

        # On ladder / in air -> find platform below
        if not current_platform:
            platforms_below = [
                p for p in self.platforms
                if p.rect.top >= self.player.rect.bottom and
                p.rect.left <= player_x <= p.rect.right
            ]
            if platforms_below:
                p = min(platforms_below, key=lambda plat: plat.rect.top)
                current_platform = p
                state['player_platform'] = p.platform_number
                self.player.current_platform_number = p.platform_number  # <-- track player platform
                state['height_from_platform'] = p.rect.top - self.player.rect.bottom


        # --- Flags ---
        state['on_ladder'] = 1 if self.player.on_ladder else 0
        state['in_air'] = 1 if (not self.player.on_ladder and self.player.change_y != 0) else 0

        # --- Ladder delta x (nearest ladder, signed) ---
        valid_ladders = []
        for lad in self.ladders:
            if getattr(lad, 'platform_number', -1) == self.player.current_platform_number:
                valid_ladders.append(lad)

        if valid_ladders:
            nearest_ladder = min(
                valid_ladders,
                key=lambda l: (l.rect.centerx - player_x) ** 2
            )
            state['ladder_dx'] = nearest_ladder.rect.centerx - player_x
        else:
            state['ladder_dx'] = 0 

        # --- Closest BARREL FACING the player (signed delta x) ---
        threatening_barrels = []
        for b in self.barrels:
            if ((b.rect.centerx < player_x and b.change_x > 0) or
                (b.rect.centerx > player_x and b.change_x < 0)):
                threatening_barrels.append(b)

        if threatening_barrels:
            closest_barrel = min(
                threatening_barrels,
                key=lambda b: (b.rect.centerx - player_x) ** 2
            )
            state['barrel_dx'] = closest_barrel.rect.centerx - player_x

        # --- Princess delta x (signed) ---
        state['princess_dx'] = self.princess.rect.centerx - player_x

        # --- Princess same platform ---
        if current_platform:
            for p in self.platforms:
                if (p.rect.left <= self.princess.rect.centerx <= p.rect.right and
                    abs(self.princess.rect.bottom - p.rect.top) < 12):
                    if p.platform_number == current_platform.platform_number:
                        state['same_platform_princess'] = 1
                    break

            # --- Platform edge deltas (signed) ---
            state['platform_left_dx'] = current_platform.rect.left - player_x
            state['platform_right_dx'] = current_platform.rect.right - player_x

        return state


    def state_to_tensor(self, state):
        # ... (נשאר זהה) ...
        state_tensor = torch.tensor(
            [
                state['player_platform'],          # 0
                state['player_x'],                 # 1
                state['height_from_platform'],     # 2
                state['on_ladder'],                # 3
                state['in_air'],                   # 4
                state['ladder_dx'],                # 5
                state['barrel_dx'],                # 6
                state['princess_dx'],              # 7
                state['same_platform_princess'],   # 8
                state['platform_left_dx'],         # 9
                state['platform_right_dx']         # 10
            ],
            dtype=torch.float32
        )
        state_tensor[0] = state_tensor[0] / 5.0  # Normalize platform number (0-5)
        state_tensor[1] = state_tensor[1] / self.screen_width  # Normalize x position
        state_tensor[2] = state_tensor[2] / self.screen_height  # Normalize height from platform
        state_tensor[5] = state_tensor[5] / self.screen_width  # Normalize ladder dx
        state_tensor[6] = state_tensor[6] / self.screen_width  # Normalize barrel dx
        state_tensor[7] = state_tensor[7] / self.screen_width  #  Normalize princess dx
        state_tensor[9] = state_tensor[9] / self.screen_width  # Normalize platform left dx
        state_tensor[10] = state_tensor[10] / self.screen_width  # Normalize platform right dx

        return state_tensor
    
    def is_player_on_platform(self):
        # ... (נשאר זהה) ...
        if not self.player:
            return False
            
        for platform in self.platforms:
            if (platform.rect.left <= self.player.rect.centerx <= platform.rect.right and
                abs(self.player.rect.bottom - platform.rect.top) < 10):
                return True
        return False
    
    def is_player_on_ladder(self):
        # ... (נשאר זהה) ...
        if not self.player:
            return False
            
        for ladder in self.ladders:
            player_center_x = self.player.rect.centerx
            ladder_center_x = ladder.rect.centerx

            horiz_tol = 32
            if abs(player_center_x - ladder_center_x) <= horiz_tol:
                if (ladder.rect.top <= self.player.rect.bottom <= ladder.rect.bottom + 24):
                    return True
        return False

    def is_player_center_on_ladder(self):
        # ... (נשאר זהה) ...
        if not self.player:
            return False
        for ladder in self.ladders:
            player_center_x = self.player.rect.centerx
            ladder_center_x = ladder.rect.centerx
            horiz_tol = 10
            if abs(player_center_x - ladder_center_x) <= horiz_tol:
                return True
        return False

    def compute_reward(self, prev_state_dict, prev_score, prev_lives):
        # =================== REWARD ===================
        reward = 0

        # 1️⃣ Step penalty חזק
        reward -= 1.0

        # 2️⃣ Penalty אם עומד במקום
        if self.player.rect.x == prev_state_dict['player_x'] and self.player.rect.y == prev_state_dict['player_y']:
            reward -= 5.0

        # 3️⃣ Losing / Winning
        if self.lives < prev_lives or (self.game_over and self.lives == 0):
            reward = -100
        elif self.score > prev_score:
            reward = +5000

        # 4️⃣ End-of-episode penalty אם עבר 5000 צעדים ולא הגיע ל-princess
        if getattr(self, 'steps', 0) >= 5000 and not getattr(self, 'reached_princess', False):
            reward -= 100

        return reward