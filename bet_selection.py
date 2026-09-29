"""Pure best-market selection shared by the prediction pipeline.

Dependency-free (stdlib only) so the decision can be unit-tested
without FBref, the Odds API, Supabase, or any third-party packages.
"""


def select_best_bet(potential_bets):
    """
    Pure best-market selection over already-created potential bets.

    A bet is valid when its 'price' is truthy, and the winner is the
    valid bet maximizing expected-value edge (prob * price) - 1.
    Returns the winning bet object itself, or None when no valid bets exist.
    """
    valid_bets = [b for b in potential_bets if b['price']]
    if not valid_bets:
        return None
    return max(valid_bets, key=lambda x: (x['prob'] * x['price']) - 1)
