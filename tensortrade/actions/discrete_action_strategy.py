# Copyright 2019 The TensorTrade Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
import numpy as np

from typing import Union
from gym.spaces import Discrete

from tensortrade.actions import ActionStrategy, TradeActionUnion, DTypeString
from tensortrade.trades import Trade, TradeType


class DiscreteActionStrategy(ActionStrategy):
    """Simple discrete strategy, which calculates the trade amount as a fraction of the total balance."""

    def __init__(self, n_actions: int = 20, instrument_symbol: str = 'BTC', max_allowed_slippage_percent: float = 1.0):
        """
        Arguments:
            n_actions: The number of bins to divide the total balance by. Defaults to 20 (i.e. 1/20, 2/20, ..., 20/20).
            instrument_symbol: The exchange symbol of the instrument being traded. Defaults to 'BTC'.
        """
        super().__init__(action_space=Discrete(n_actions), dtype=np.int64)

        self.n_actions = n_actions
        self.instrument_symbol = instrument_symbol

    @property
    def dtype(self) -> DTypeString:
        """A type or str corresponding to the dtype of the `action_space`."""
        return self._dtype

    @dtype.setter
    def dtype(self, dtype: DTypeString):
        raise ValueError(
            'Cannot change the dtype of a `SimpleDiscreteStrategy` due to the requirements of `gym.spaces.Discrete` spaces. ')

    @property
    def n_splits(self) -> int:
        return self.n_actions / len(TradeType)

    def _get_trade_type(self, action:TradeActionUnion) -> TradeType:
        """calculates the trade type based off of the action value passed
        params:
            action: the action between the range of the n_actions
        returns:
            TradeType
        """
        return TradeType(action % len(TradeType))

    def _get_trade_amount(self, action:TradeActionUnion) -> float:
        amount = int(action / len(TradeType)) * float(1 / self.n_splits) + (1 / self.n_splits)
        return amount

    def get_trade(self, action: TradeActionUnion) -> Trade:
        """The trade type is determined by `action % len(TradeType)`, and the trade amount is determined by the multiplicity of the action.

        For example, 1 = LIMIT_BUY|0.25, 2 = MARKET_BUY|0.25, 6 = LIMIT_BUY|0.5, 7 = MARKE
        T_BUY|0.5, etc.
        """

        trade_type = self._get_trade_type(action)
        trade_amount = self._get_trade_amount(action)

        base_precision = self._exchange.base_precision
        instrument_precision = self._exchange.instrument_precision

        amount_held = self._exchange.instrument_balance(self.instrument_symbol)
        current_price = self._exchange.current_price(symbol=self.instrument_symbol)

        balance = self._exchange.balance

        if trade_type.is_buy:
            # as an aditional barrier to overflowing the balance,
            # we reserve 2% of our total balance for unseen slip and comissions.
            trade_amount = round(balance * 0.98 * trade_amount / current_price, instrument_precision)
        elif trade_type.is_sell:
            trade_amount = round(amount_held * trade_amount, instrument_precision)

        return Trade(self.instrument_symbol, trade_type, trade_amount, current_price)