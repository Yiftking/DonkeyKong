import pygame
import torch
import os
import wandb

from environment import Environment
from character import Character
from AI_agent import DQN_Agent


def main():
    num = 1
    pygame.init()

    screen_width = 1500
    screen_height = 820
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Donkey Kong Trainer")

    agent = DQN_Agent()

    episodes = 20000   # CHANGED FROM 500
    best_score = 0

    wandb.init(
        project="donkey-kong-dqn",
        config={
            "learning_rate": agent.learning_rate,
            "gamma": agent.gamma,
            "batch_size": agent.batch_size,
            "epsilon_decay": agent.epsilon_decay
        }
    )

    # ✅ Buffers for 100-episode averaging
    reward_buffer = []
    score_buffer = []
    platform_buffer = []

    for episode in range(episodes):

        env = Environment(screen_width, screen_height)
        character = Character(50, screen_height - 60)
        env.add_player(character)

        state = env.state_to_tensor(env.get_state())
        total_reward = 0
        done = False
        step = 0
        while not done:
            step += 1
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

            action = agent.get_action([], state)
            next_state, reward, done = env.step(action)

            agent.remember(state, action, reward, next_state, done)
            agent.train()

            state = next_state
            total_reward += reward
            if step > 5000:
                break
            # screen.fill((0, 0, 0))
            # env.render(screen)
            # pygame.display.flip()

        best_score = max(best_score, env.score)

        print(f"Episode {episode} | Score: {env.score} | Reward: {total_reward} | Best: {best_score}")

        # ✅ Store values for averaging
        reward_buffer.append(total_reward)
        score_buffer.append(env.score)
        platform_buffer.append(env.player.current_platform_number)
        # ✅ Log every 100 episodes
        if episode % 100 == 0 and episode != 0:
            avg_reward = sum(reward_buffer) / len(reward_buffer)
            avg_score = sum(score_buffer) / len(score_buffer)
            avg_platform = sum(platform_buffer) / len(platform_buffer)

            wandb.log({
                "episode": episode,
                "avg_reward_100": avg_reward,
                "avg_score_100": avg_score,
                "avg_platform_100": avg_platform,
                "epsilon": agent.epsilon,
                "best_score": best_score
                
            })

            reward_buffer.clear()
            score_buffer.clear()
            platform_buffer.clear()

        if env.score >= best_score:
            best_score = env.score
            torch.save(agent.model.state_dict(), f"Data/best_dqn_model_{num}.pth")
            torch.save(agent.target_model.state_dict(), f"Data/best_dqn_target_model_{num}.pth")
            torch.save(agent.epsilon, f"Data/best_epsilon_{num}.pth")
            print("New Best Model Saved")

        agent.epsilon = max(agent.epsilon_min,
                    agent.epsilon * agent.epsilon_decay)

    pygame.quit()


if __name__ == "__main__":
    main()