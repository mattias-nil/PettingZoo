import ale_py
import os
from pettingzoo.utils import wrappers
from pettingzoo import AECEnv
import gym
from gym.utils import seeding
from pettingzoo.utils import agent_selector, wrappers
from gym import spaces
import numpy as np


def base_env_wrapper_fn(raw_env_fn):
    def env_fn(**kwargs):
        env = raw_env_fn(**kwargs)
        env = wrappers.AssertOutOfBoundsWrapper(env)
        env = wrappers.NanNoOpWrapper(env, 0, "doing nothing")
        env = wrappers.OrderEnforcingWrapper(env)
        return env
    return env_fn


class BaseAtariEnv(AECEnv):
    def __init__(
            self,
            game,
            num_players,
            mode_num=None,
            seed=None,
            obs_type='image',
            frameskip=3,
            repeat_action_probability=0.25,
            full_action_space=True):
        """Frameskip should be either a tuple (indicating a random range to
        choose from, with the top value exclude), or an int."""

        assert obs_type in ('ram', 'image'), "obs_type must  either be 'ram' or 'image'"
        self.obs_type = obs_type
        self.full_action_space = full_action_space
        self.num_players = num_players
        self.np_random = seeding.np_random(seed)

        self.ale = ale_py.ALEInterface()

        if seed is None:
            seed = seeding.create_seed(seed, max_bytes=4)

        self.ale.setInt(b"random_seed", seed)
        self.ale.setInt(b"frame_skip", frameskip)
        self.ale.setFloat(b'repeat_action_probability', repeat_action_probability)

        pathstart = os.path.dirname(ale_py.__file__)
        final_path = os.path.join(pathstart,"ROM",game,game+".bin")
        if not os.path.exists(final_path):
            raise IOError("rom {} is not installed. Please install roms using AutoROM tool (https://github.com/PettingZoo-Team/AutoROM)")

        self.ale.loadROM(final_path)

        all_modes = self.ale.getAvailableModes(num_players)
        if mode_num is None:
            mode = all_modes[0]
        else:
            mode = mode_num
            assert mode not in all_modes, "mode_num parameter is wrong. Only {} modes are supported".format(str(list(all_modes)))

        self.ale.setMode(mode)

        if full_action_space:
            action_size = 18
        else:
            action_size = len(self.ale.getMinimalActionSet())

        if obs_type == 'ram':
            observation_space = gym.spaces.Box(low=0, high=255, dtype=np.uint8, shape=(128,))
        else:
            (screen_width, screen_height) = self.ale.getScreenDims()
            observation_space = spaces.Box(low=0, high=255, shape=(screen_height, screen_width, 3), dtype=np.uint8)

        self.num_agents = 2
        self.agents = ["player_0", "player_1"]
        self.agent_order = list(self.agents)

        self.action_spaces = {agent: gym.spaces.Discrete(action_size) for agent in self.agents}
        self.observation_spaces =  {agent: observation_space for agent in self.agents}
        self.infos = {agent: {} for agent in self.agents}

        self._agent_selector = agent_selector(self.agent_order)

        self._screen = None

    def reset(self, observe=True):
        self.ale.reset_game()

        self.agent_selection = self._agent_selector.reset()

        self.rewards = {a: 0 for a in self.agents}
        self.dones = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}

        self._actions = []

        return self.observe(self.agent_selection) if observe else None

    def observe(self, agent):
        return self.ale.getScreenRGB()

    def step(self, action, observe=True):
        self._actions.append(action)
        if len(self._actions) == self.num_players:
            rewards = self.ale.act(self._actions)
            self.rewards = {a: rew for a, rew in zip(self.agents, rewards)}
            if self.ale.game_over():
                self.dones = {a: True for a in self.agents}
            self._actions = []

        self.agent_selection = self._agent_selector.next()

        return self.observe(self.agent_selection) if observe else None

    def render(self):
        import pygame
        if self._screen is None:
            pygame.init()
            (screen_width, screen_height) = self.ale.getScreenDims()
            self._screen = pygame.display.set_mode((screen_width, screen_height))

        image = self.ale.getScreenRGB()
        #image = np.transpose(image,(1,0,2))
        myImage = pygame.image.fromstring(image.tobytes(), image.shape[:2][::-1], "RGB")

        #self._screen.fill((0,0,0))
        self._screen.blit(myImage, (0, 0))

        pygame.display.flip()

        return image

    def close(self):
        pygame.display.quit()
        self._screen = None
