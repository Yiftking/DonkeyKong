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

            # Ensure player sprite updates (animation/image switching)
            try:
                self.player.update()
            except Exception:
                pass

    def get_state(self):
        # Default state values
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
        # CHANGED: Use platform ID matching
        valid_ladders = []
        for lad in self.ladders:
            # Check if ladder belongs to the current platform
            # We use -1 default to avoid crash if attribute missing (though we just added it)
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
        # END CHANGED SECTION

        # --- Closest BARREL FACING the player (signed delta x) ---
        threatening_barrels = []
        for b in self.barrels:
            # Barrel is facing the player
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
        """
        Convert state dictionary to a fixed-size state tensor (length = 11).
        """

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
        # Check if player is on any platform
        if not self.player:
            return False
            
        for platform in self.platforms:
            if (platform.rect.left <= self.player.rect.centerx <= platform.rect.right and
                abs(self.player.rect.bottom - platform.rect.top) < 10):
                return True
        return False
    
    def is_player_on_ladder(self):
        # Check if player is touching any ladder
        if not self.player:
            return False
            
        for ladder in self.ladders:
            # Check if player's center is aligned with ladder
            # Allow a bit more tolerance horizontally and vertically for easier ladder grabbing
            player_center_x = self.player.rect.centerx
            ladder_center_x = ladder.rect.centerx

            # Horizontal tolerance
            horiz_tol = 32
            if abs(player_center_x - ladder_center_x) <= horiz_tol:
                # Vertical tolerance: only within ladder bounds (not above it)
                if (ladder.rect.top <= self.player.rect.bottom <= ladder.rect.bottom + 24):
                    return True
        return False

    def is_player_center_on_ladder(self):
        # Return True if the player's horizontal center is directly over any ladder
        if not self.player:
            return False
        for ladder in self.ladders:
            if ladder.rect.left <= self.player.rect.centerx <= ladder.rect.right:
                # Also ensure vertical overlap with ladder extent (allow small tolerance)
                if (ladder.rect.top - 24 <= self.player.rect.bottom <= ladder.rect.bottom + 24):
                    return True
        return False

    def get_ladder_under_center(self):
        """Return the ladder sprite under the player's horizontal center (or None)."""
        if not self.player:
            return None
        for ladder in self.ladders:
            if ladder.rect.left <= self.player.rect.centerx <= ladder.rect.right:
                if (ladder.rect.top - 24 <= self.player.rect.bottom <= ladder.rect.bottom + 24):
                    return ladder
        return None
    
    def step(self, action):
        """
        Execute action, calculate reward, and return result.
        Returns: (next_state_tensor, reward, done)
        """
        if not self.player:
            return self.state_to_tensor(self.get_state()), 0, True

        # 1. State BEFORE action (used for reward shaping)
        prev_state_dict = self.get_state()
        prev_y = self.player.rect.y
        prev_lives = self.lives
        prev_score = self.score
        prev_on_ladder = self.player.on_ladder
        
        # --- EXECUTE PHYSICS ---
        
        # Ladder grabbing logic
        ladder_under_center = self.get_ladder_under_center()
        target_ladder = ladder_under_center
        if not self.player.on_ladder and not target_ladder:
            for lad in self.ladders:
                if abs(self.player.rect.centerx - lad.rect.centerx) <= 40 and \
                   (lad.rect.top - 40 <= self.player.rect.bottom <= lad.rect.bottom + 40):
                    target_ladder = lad
                    break

        if not self.player.on_ladder and target_ladder:
            if action == 3 or (action == 4 and not self.is_player_on_platform()):
                self.player.on_ladder = True
                # reset hang counter when first grabbing ladder
                try:
                    self.player.ladder_hold_counter = 0
                    self.player.just_grabbed_ladder = True  # Flag to reward ladder grab
                except Exception:
                    pass
                self.player.change_y = 0
                self.player.is_jumping = False
                self.player.rect.centerx = target_ladder.rect.centerx
                if self.is_player_on_platform():
                    self.player.rect.y -= 2
                self.player.change_x = 0
                if action == 3: self.player.move_up()
                elif action == 4: self.player.move_down()

        if self.player.on_ladder:
            if action == 3:
                self.player.move_up()
                self._align_to_ladder()
                self._check_ladder_to_platform_transition()
            elif action == 4:
                can_move_down = True
                if self.is_player_on_platform():
                    if ladder_under_center and abs(self.player.rect.bottom - ladder_under_center.rect.bottom) < 10:
                        can_move_down = False
                if can_move_down: self.player.move_down()
                else: self.player.stop_vertical()
                self._align_to_ladder()
            else:
                self.player.stop_vertical()

            if action == 2 or action == 7: self.player.move_left()
            elif action == 1 or action == 6: self.player.move_right()
            else: self.player.stop_horizontal()
            
            if not ladder_under_center and action != 3 and action != 4:
                self.player.on_ladder = False
                self.player.change_y = 0

        else:
            # Not on ladder
            was_on_ladder = self.player.on_ladder
            self.player.on_ladder = False
            
            if action == 2 or action == 7:
                if was_on_ladder: self.player.change_x = -self.player.speed
                else: self.player.move_left()
            elif action == 1 or action == 6:
                if was_on_ladder: self.player.change_x = self.player.speed
                else: self.player.move_right()
            elif action != 5: # Don't stop horizontal if Jumping
                self.player.stop_horizontal()
            
            if (action == 5 or action == 6 or action == 7 or action == 3) and not target_ladder:
                if self.is_player_on_platform() and not self.player.is_jumping:
                    self.player.jump()

        # Update physics
        self.update()
        # --- Track ladder hold (frames holding ladder without moving) ---
        try:
            if self.player.on_ladder:
                # consider tiny movement as moving
                if abs(self.player.change_y) < 0.5:
                    self.player.ladder_hold_counter = getattr(self.player, 'ladder_hold_counter', 0) + 1
                else:
                    self.player.ladder_hold_counter = 0
            else:
                self.player.ladder_hold_counter = 0
        except Exception:
            pass
        # Detect if a jump actually happened
        next_state_dict = self.get_state()

        jump_happened = (
        prev_state_dict['in_air'] == 0 and
        next_state_dict['in_air'] == 1 and
        not next_state_dict['on_ladder']
    )


        # 2. State AFTER action
        #next_state_dict = self.get_state()

        # --- REWARD CALCULATION (IMPROVED) ---
        reward = 0

        # A. Reward for climbing UP (y decreases)
        diff_y = prev_y - self.player.rect.y
        if diff_y > 0:
            reward += diff_y * 5.0  # Increased reward for going up

        # B. Distance Shaping: Reward getting closer to LADDER
        if not self.player.on_ladder:
            prev_lad_dist = abs(prev_state_dict['ladder_dx'])
            curr_lad_dist = abs(next_state_dict['ladder_dx'])

            if curr_lad_dist < prev_lad_dist:
                reward += 3.0  # Increased reward for moving toward ladder
            elif curr_lad_dist > prev_lad_dist:
                reward -= 3.0  # Increased penalty for moving away

        # C. Distance Shaping: Reward getting closer to PRINCESS
        prev_prin_dist = abs(prev_state_dict['princess_dx'])
        curr_prin_dist = abs(next_state_dict['princess_dx'])
        if curr_prin_dist < prev_prin_dist:
            reward += 2.0  # Increased reward for moving toward princess

        # D. Reward for jumping over barrels
        if jump_happened:
            barrel_distance = abs(prev_state_dict['barrel_dx'])

            if barrel_distance > 200:
                reward -= 10  # Increased penalty for irrelevant jumps
            elif 80 < barrel_distance <= 200:
                reward -= 5  # Increased penalty for distant barrels
            else:
                reward += 5  # Reduced reward for close barrels

        # E. Penalty for staying still
        if self.player.rect.x == prev_state_dict['player_x'] and self.player.rect.y == prev_state_dict['player_y']:
            reward -= 2.0  # Penalty for not moving

        # F. Survival / Winning / Losing
        if self.lives < prev_lives or (self.game_over and self.lives == 0):
            reward = -100

        if self.score > prev_score:
            reward = +5000

        # G. Living penalty (encourage speed)
        reward -= 1

        # H. Reward for grabbing a ladder (encourages ladder use)
        if self.player.on_ladder and not prev_on_ladder:
            reward += 10  # Reward for using ladders

        # G. Reward for reaching platform via ladder (successful climb)
        if not self.player.on_ladder and prev_on_ladder:
            # Successfully exited ladder, likely reached a platform
            reward += 40  # Strong reward for successful climb

        # H. Scaled penalty for prolonged hanging (starts after 30 frames, not abrupt)
        hold_cnt = getattr(self.player, 'ladder_hold_counter', 0)
        if hold_cnt > 30:
            # Scale penalty: 0.3 per extra frame beyond 30
            hang_penalty = (hold_cnt - 30) * 0.3
            reward -= hang_penalty

        # Return the new tensor state, the reward, and done flag
        next_state = self.state_to_tensor(next_state_dict)
        return next_state, reward, self.game_over

    def _align_to_ladder(self):
        """Smoothly align character to ladder center when climbing"""
        for ladder in self.ladders:
            if abs(self.player.rect.centerx - ladder.rect.centerx) <= 40:
                diff = ladder.rect.centerx - self.player.rect.centerx
                if abs(diff) > 2:
                    self.player.rect.x += diff * 0.3
                else:
                    self.player.rect.centerx = ladder.rect.centerx
                break

    def _check_ladder_to_platform_transition(self):
        if not self.player.on_ladder:
            return
            
        # Find the ladder we are currently on
        current_ladder = self.get_ladder_under_center()
        if not current_ladder:
            return

        # Only transition if we are closer to the top of the ladder than the bottom
        if abs(self.player.rect.bottom - current_ladder.rect.bottom) < abs(self.player.rect.bottom - current_ladder.rect.top):
            return
            
        for platform in self.platforms:
            if (self.player.rect.bottom <= platform.rect.top + 8 and 
                self.player.rect.bottom >= platform.rect.top - 20 and
                platform.rect.left - 30 <= self.player.rect.centerx <= platform.rect.right + 30):
                self.player.on_ladder = False
                self.player.rect.bottom = platform.rect.top
                self.player.change_y = 0
                self.player.stop_vertical()
                break

    def render(self, screen):
        """Render the game state"""
        self.platforms.draw(screen)
        self.ladders.draw(screen)
        self.barrels.draw(screen)
        if self.player:
            screen.blit(self.player.image, self.player.rect)
        screen.blit(self.donkey_kong.image, self.donkey_kong.rect)
        screen.blit(self.princess.image, self.princess.rect)

    def close(self):
        """Clean up pygame resources"""
        pygame.quit()