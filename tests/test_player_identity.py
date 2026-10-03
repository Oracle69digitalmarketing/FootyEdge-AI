"""Objective 7: canonical player identity resolver/registration tests (offline only).

No network, no database, no live provider APIs, no production Supabase.
Stub Supabase enforces the post-005 contract: sequence-generated players.id,
NOT NULL mapping/alias columns, UNIQUE grains, and FK targets.
"""
import ast
import inspect
from pathlib import Path

import pytest

import player_identity as pi
from player_identity import (
    PlayerIdentityConflictError,
    PlayerIdentityError,
    UnknownPlayerIdentityError,
    canonicalize_player_name,
    fetch_player_aliases,
    fetch_player_mappings,
    fetch_players,
    register_player,
    resolve_player,
)

_REPO = Path(__file__).resolve().parent.parent
_MODULE_SRC = (_REPO / "player_identity.py").read_text()


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table, columns):
        self._table = table
        self._columns = columns
        self._filters = []

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def execute(self):
        rows = [r for r in self._table.rows
                if all(r.get(c) == v for c, v in self._filters)]
        if self._columns == ["*"]:
            return _Result([dict(r) for r in rows])
        return _Result(
            [{c: r.get(c) for c in self._columns} for r in rows]
        )


class _Insert:
    """Mirrors postgrest-py, enforcing the post-005 PK/UNIQUE/NOT NULL/FK guards."""

    def __init__(self, db, table, row):
        self._db = db
        self._table = table
        self._row = row

    def execute(self):
        if self._table._fail_once:
            self._table._fail_once = False
            raise ValueError("simulated concurrent write conflict")
        for col in self._table._not_null:
            if self._row.get(col) is None:
                raise ValueError(f"null value in column {col!r}")
        for keys in self._table._unique_keys:
            key = tuple(self._row.get(k) for k in keys)
            for existing in self._table.rows:
                if tuple(existing.get(k) for k in keys) == key:
                    raise ValueError(f"duplicate key {keys}={key}")
        for col, (target_table, target_col) in self._table._fk.items():
            value = self._row.get(col)
            if value is None:
                continue
            valid = {r.get(target_col) for r in self._db._tables[target_table].rows}
            if value not in valid:
                raise ValueError(f"foreign key violation {col}={value!r}")
        stored = dict(self._row)
        if self._table._seq and stored.get("id") is None:
            stored["id"] = self._table._next_id()
        self._table.rows.append(stored)
        return _Result([stored])


class _Table:
    def __init__(self, rows=(), unique_keys=(), not_null=(), fk=None, seq=False):
        self.rows = [dict(r) for r in rows]
        self._unique_keys = unique_keys
        self._not_null = not_null
        self._fk = fk or {}
        self._seq = seq
        self._seq_next = max([r.get("id") or 0 for r in self.rows] + [0]) + 1
        self._fail_once = False

    def _next_id(self):
        value = self._seq_next
        self._seq_next += 1
        return value

    def select(self, columns):
        cols = [c.strip() for c in columns.split(",")]
        return _Query(self, cols)

    def insert(self, row):
        return _Insert(self._db_ref, self, row)


class StubSupabase:
    """Fake with the PK/UNIQUE/NOT NULL/FK guards the 005 schema enforces."""

    def __init__(self, players=(), mappings=(), aliases=(), history=(), teams=()):
        self._tables = {
            "players": _Table(
                players, unique_keys=[("id",)], not_null=("name",), seq=True),
            "player_identity_sources": _Table(
                mappings,
                unique_keys=[("source", "external_player_id")],
                not_null=("player_id", "source", "external_player_id"),
                fk={"player_id": ("players", "id")},
            ),
            "player_aliases": _Table(
                aliases,
                unique_keys=[("alias", "source")],
                not_null=("player_id", "alias", "source"),
                fk={"player_id": ("players", "id")},
            ),
            "player_team_history": _Table(
                history,
                not_null=("player_id", "team_id"),
                fk={"player_id": ("players", "id"),
                    "team_id": ("teams", "id")},
            ),
            "teams": _Table(teams),
        }
        for table in self._tables.values():
            table._db_ref = self

    def table(self, name):
        return self._tables[name]


def _db():
    return StubSupabase(teams=[{"id": 10}, {"id": 20}])


def _counts(db):
    return {name: len(db.table(name).rows) for name in (
        "players", "player_identity_sources",
        "player_aliases", "player_team_history")}


# --- canonical registration: sequence IDs, never assigned ---


def test_register_mints_sequence_id():
    db = _db()
    pid, name = register_player(name="Alex Silva", supabase=db)
    assert isinstance(pid, int) and pid >= 1
    assert name == "Alex Silva"
    assert db.table("players").rows == [{"id": pid, "name": "Alex Silva"}]


def test_ids_are_sequence_generated_not_caller_assigned():
    db = _db()
    first, _ = register_player(name="Alex Silva", supabase=db)
    second, _ = register_player(name="Alex Silva", supabase=db)
    assert second == first + 1  # namesakes coexist; IDs come from the sequence
    assert 'insert({"name": canonical})' in _MODULE_SRC  # no id passed
    assert "players_id_seq" not in _MODULE_SRC  # sequences never reset/touched


def test_permanent_id_independent_of_team():
    db = _db()
    pid, _ = register_player(name="Alex Silva", supabase=db, team_id=10)
    assert resolve_player(player_id=pid, players=fetch_players(db)) == (
        pid, "Alex Silva")
    db.table("player_team_history").insert(
        {"player_id": pid, "team_id": 20,
         "competition_id": None, "season_id": None}).execute()
    assert resolve_player(player_id=pid, players=fetch_players(db)) == (
        pid, "Alex Silva")


def test_transfer_does_not_change_identity():
    db = _db()
    pid, _ = register_player(name="Alex Silva", supabase=db, team_id=10)
    history = db.table("player_team_history").rows
    assert history == [{"player_id": pid, "team_id": 10,
                        "competition_id": None, "season_id": None}]
    assert resolve_player(player_id=pid, players=fetch_players(db))[0] == pid


def test_team_membership_is_optional():
    db = _db()
    register_player(name="Free Agent", supabase=db)
    assert db.table("player_team_history").rows == []


def test_team_id_must_be_integer():
    with pytest.raises(TypeError):
        register_player(name="Alex Silva", supabase=_db(), team_id="10")


# --- namesake rule: same name, distinct players, bare name conflicts ---


def test_namesakes_coexist_and_bare_name_conflicts():
    db = _db()
    first, _ = register_player(name="Alex Silva", supabase=db)
    second, _ = register_player(name="Alex Silva", supabase=db)
    assert first != second
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(name="Alex Silva", players=fetch_players(db))
    # ... but each resolves exactly by canonical ID (never first-row pick).
    assert resolve_player(player_id=first, players=fetch_players(db))[0] == first
    assert resolve_player(player_id=second, players=fetch_players(db))[0] == second


# --- provider mapping round-trip, isolation, conflict, rotation ---


def test_provider_mapping_round_trip():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    mappings = fetch_player_mappings(db, source="api-football")
    assert mappings == [{"player_id": pid, "source": "api-football",
                         "external_player_id": "33"}]
    assert resolve_player(
        source="api-football", external_player_id="33",
        players=fetch_players(db), player_mappings=mappings) == (
            pid, "Alex Silva")


def test_source_isolation():
    db = _db()
    first, _ = register_player(
        name="Alex Silva", supabase=db,
        source="provider-a", external_player_id="33")
    second, _ = register_player(
        name="Alex S.", supabase=db,
        source="provider-b", external_player_id="33")
    assert first != second
    assert resolve_player(
        source="provider-a", external_player_id="33",
        players=fetch_players(db),
        player_mappings=fetch_player_mappings(db)) == (first, "Alex Silva")
    assert resolve_player(
        source="provider-b", external_player_id="33",
        players=fetch_players(db),
        player_mappings=fetch_player_mappings(db)) == (second, "Alex S.")


def test_duplicate_provider_grain_rejected_by_store():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    with pytest.raises(ValueError, match="duplicate key"):
        db.table("player_identity_sources").insert(
            {"player_id": pid + 999, "source": "api-football",
             "external_player_id": "33"}).execute()


def test_same_grain_same_player_is_idempotent():
    db = _db()
    first, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    second, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    assert second == first
    assert len(db.table("players").rows) == 1
    assert len(db.table("player_identity_sources").rows) == 1


def test_same_grain_other_player_is_conflict():
    db = _db()
    register_player(name="Alex Silva", supabase=db,
                    source="api-football", external_player_id="33")
    with pytest.raises(PlayerIdentityConflictError):
        register_player(name="Alex S.", supabase=db,
                        source="api-football", external_player_id="33")
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            source="api-football", external_player_id="33",
            players=fetch_players(db),
            player_mappings=fetch_player_mappings(db) + [
                {"source": "api-football",
                 "external_player_id": "33", "player_id": 4242}])


def test_provider_id_rotation_keeps_canonical_id():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    db.table("player_identity_sources").insert(
        {"player_id": pid, "source": "api-football",
         "external_player_id": "34"}).execute()
    for external in ("33", "34"):
        assert resolve_player(
            source="api-football", external_player_id=external,
            players=fetch_players(db),
            player_mappings=fetch_player_mappings(db)) == (pid, "Alex Silva")


def test_dangling_mapping_target_is_conflict():
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            source="api-football", external_player_id="33",
            players=[{"id": 1, "name": "Alex Silva"}],
            player_mappings=[{"source": "api-football",
                              "external_player_id": "33",
                              "player_id": 999}])


# --- aliases: pointers, ambiguity, disagreement, windows ---


def test_alias_resolution():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        alias="A. Silva", alias_source="provider-a")
    assert resolve_player(
        alias="A. Silva", alias_source="provider-a",
        players=fetch_players(db),
        aliases=fetch_player_aliases(db)) == (pid, "Alex Silva")


def test_alias_ambiguity_is_conflict():
    db = _db()
    first, _ = register_player(name="Alex Silva", supabase=db)
    second, _ = register_player(name="Andre Silva", supabase=db)
    db.table("player_aliases").insert(
        {"player_id": first, "alias": "A. Silva",
         "source": "provider-a"}).execute()
    # The UNIQUE(alias, source) grain blocks a second stored row for the
    # same alias; divergent in-memory rows fail closed in the resolver.
    divergent = fetch_player_aliases(db) + [
        {"player_id": second, "alias": "A. Silva", "source": "provider-a"}]
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            alias="A. Silva", alias_source="provider-a",
            players=fetch_players(db), aliases=divergent)


def test_alias_provider_disagreement_is_conflict():
    db = _db()
    first, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    second, _ = register_player(name="Andre Silva", supabase=db)
    db.table("player_aliases").insert(
        {"player_id": second, "alias": "A. Silva",
         "source": "api-football"}).execute()
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            source="api-football", external_player_id="33",
            alias="A. Silva",
            players=fetch_players(db),
            player_mappings=fetch_player_mappings(db),
            aliases=fetch_player_aliases(db))


def test_alias_canonical_disagreement_is_conflict():
    db = _db()
    first, _ = register_player(name="Alex Silva", supabase=db)
    second, _ = register_player(name="Andre Silva", supabase=db)
    db.table("player_aliases").insert(
        {"player_id": first, "alias": "A. Silva",
         "source": "provider-a"}).execute()
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            name="Andre Silva", alias="A. Silva", alias_source="provider-a",
            players=fetch_players(db), aliases=fetch_player_aliases(db))


def test_validity_windows_are_recorded_not_consulted():
    db = _db()
    pid, _ = register_player(name="Alex Silva", supabase=db)
    db.table("player_aliases").rows.append(
        {"player_id": pid, "alias": "A. Silva", "source": "provider-a",
         "valid_from": "1990-01-01", "valid_to": "1991-01-01"})
    assert resolve_player(
        alias="A. Silva", alias_source="provider-a",
        players=fetch_players(db),
        aliases=fetch_player_aliases(db)) == (pid, "Alex Silva")
    module_ast = ast.parse(_MODULE_SRC)
    for node in ast.walk(module_ast):
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_player":
            names = {n.attr if isinstance(n, ast.Attribute) else n.id
                     for n in ast.walk(node)
                     if isinstance(n, (ast.Attribute, ast.Name))}
            assert "valid_from" not in names and "valid_to" not in names


def test_dangling_alias_target_is_conflict():
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            alias="A. Silva", alias_source="provider-a",
            players=[{"id": 1, "name": "Alex Silva"}],
            aliases=[{"alias": "A. Silva", "source": "provider-a",
                      "player_id": 999}])


# --- Unknown / invalid / fail-closed behavior ---


def test_unknown_provider_identity():
    db = _db()
    register_player(name="Alex Silva", supabase=db,
                    source="api-football", external_player_id="33")
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(
            source="api-football", external_player_id="34",
            players=fetch_players(db),
            player_mappings=fetch_player_mappings(db))


def test_unknown_alias_name_and_id():
    db = _db()
    register_player(name="Alex Silva", supabase=db)
    players = fetch_players(db)
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(alias="Nobody", players=players,
                       aliases=fetch_player_aliases(db))
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(name="Nobody", players=players)
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(player_id=4242, players=players)


def test_no_reference_supplied_is_unknown():
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(players=[{"id": 1, "name": "Alex Silva"}])


def test_partial_provider_reference_is_unknown():
    players = [{"id": 1, "name": "Alex Silva"}]
    mappings = [{"source": "api-football", "external_player_id": "33",
                 "player_id": 1}]
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(source="api-football", players=players,
                       player_mappings=mappings)
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(external_player_id="33", players=players,
                       player_mappings=mappings)


def test_non_text_external_id_rejected_without_cast():
    with pytest.raises(TypeError):
        resolve_player(source="api-football", external_player_id=33,
                       players=[], player_mappings=[])
    with pytest.raises(TypeError):
        fetch_player_mappings(_db(), source=39)


def test_invalid_player_id_rejected():
    with pytest.raises(TypeError):
        resolve_player(player_id="1", players=[])
    with pytest.raises(TypeError):
        resolve_player(player_id=True, players=[])


def test_invalid_names_rejected():
    with pytest.raises(ValueError):
        canonicalize_player_name("")
    with pytest.raises(ValueError):
        canonicalize_player_name(39)
    with pytest.raises(ValueError):
        register_player(name="  ", supabase=_db())


def test_no_fuzzy_or_inferred_resolution():
    players = [{"id": 1, "name": "Alex Silva"}]
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(name="AlexSilva", players=players)
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(name="alex silva", players=players)
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(name="Alex Silva ", players=[])  # trailing space, no rows
    params = set(inspect.signature(resolve_player).parameters)
    assert not (params & {"date", "match_date", "fixture", "team_name",
                          "league", "season"})
    assert canonicalize_player_name("  Alex   Silva ") == "Alex Silva"


def test_errors_are_value_errors():
    assert issubclass(UnknownPlayerIdentityError, PlayerIdentityError)
    assert issubclass(PlayerIdentityConflictError, PlayerIdentityError)
    assert issubclass(PlayerIdentityError, ValueError)


# --- read-only resolution: nothing created, ever ---


def test_failed_resolution_writes_nothing():
    db = _db()
    register_player(name="Alex Silva", supabase=db)
    before = _counts(db)
    for call in (
        lambda: resolve_player(
            source="api-football", external_player_id="99",
            players=fetch_players(db),
            player_mappings=fetch_player_mappings(db)),
        lambda: resolve_player(name="Nobody", players=fetch_players(db)),
        lambda: resolve_player(player_id=4242, players=fetch_players(db)),
    ):
        with pytest.raises(UnknownPlayerIdentityError):
            call()
    assert _counts(db) == before


def test_resolver_and_fetchers_never_write():
    module_ast = ast.parse(_MODULE_SRC)
    for node in ast.walk(module_ast):
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_player":
            called = {n.attr for n in ast.walk(node)
                      if isinstance(n, ast.Attribute)}
            assert not (called & {"insert", "upsert", "update", "delete",
                                  "create", "execute"}), node.name
        if isinstance(node, ast.FunctionDef) and node.name.startswith("fetch_"):
            # Retrieval layer may read (execute) but never writes.
            called = {n.attr for n in ast.walk(node)
                      if isinstance(n, ast.Attribute)}
            assert not (called & {"insert", "upsert", "update", "delete",
                                  "create"}), node.name


def test_legacy_external_id_column_untouched():
    # The prohibition is documented in prose; no CODE may reference the
    # legacy column (SELECT/INSERT/UPDATE keys or filters).
    code = _MODULE_SRC.replace("external_player_id", "")
    docstring = ast.get_docstring(ast.parse(_MODULE_SRC)) or ""
    code_without_prose = code.replace(docstring, "")
    assert "external_id" not in code_without_prose
    assert fetch_players(_db()) == []
    db = _db()
    register_player(name="Alex Silva", supabase=db)
    assert set(fetch_players(db)[0]) == {"id", "name"}


def test_no_cross_namespace_writes():
    for forbidden in ('"teams"', "'teams'", "team_aliases",
                      "team_identity_sources", "match_provider_identity",
                      "competitions", "seasons", "predictions", "value_bets"):
        assert forbidden not in _MODULE_SRC


# --- registration boundaries: evidence-only, race-safe ---


def test_partial_provider_evidence_rejected_without_writes():
    db = _db()
    before = _counts(db)
    with pytest.raises(ValueError):
        register_player(name="Alex Silva", supabase=db,
                        source="api-football")
    with pytest.raises(ValueError):
        register_player(name="Alex Silva", supabase=db,
                        external_player_id="33")
    assert _counts(db) == before


def test_sourceless_alias_rejected_without_writes():
    db = _db()
    before = _counts(db)
    with pytest.raises(ValueError):
        register_player(name="Alex Silva", supabase=db, alias="A. Silva")
    assert _counts(db) == before


def test_registration_never_fabricates_provider_ids():
    db = _db()
    pid, _ = register_player(name="Alex Silva", supabase=db)
    assert db.table("player_identity_sources").rows == []
    with pytest.raises(TypeError):
        register_player(name="Andre Silva", supabase=db,
                        source="api-football", external_player_id=34)
    assert _counts(db) == {"players": 1, "player_identity_sources": 0,
                           "player_aliases": 0, "player_team_history": 0}


def test_registration_race_on_player_row_adopts_singleton():
    db = _db()
    # A concurrent registration commits first; our insert then collides and
    # the fallback adopts the single visible row (insert-then-verify).
    db.table("players").rows.append({"id": 1, "name": "Alex Silva"})
    db.table("players")._seq_next = 2
    db.table("players")._fail_once = True
    pid, name = register_player(name="Alex Silva", supabase=db)
    assert (pid, name) == (1, "Alex Silva")
    assert len(db.table("players").rows) == 1


def test_registration_race_on_mapping_is_idempotent_or_conflict():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33")
    db.table("player_identity_sources")._fail_once = True
    assert register_player(
        name="Alex Silva", supabase=db,
        source="api-football", external_player_id="33") == (pid, "Alex Silva")
    db.table("player_identity_sources")._fail_once = True
    with pytest.raises(PlayerIdentityConflictError):
        register_player(
            name="Andre Silva", supabase=db,
            source="api-football", external_player_id="33")


def test_registration_never_infers_from_team_names():
    db = _db()
    pid, name = register_player(
        name="Arsenal", supabase=db, team_id=10)  # team-named player: no link
    assert (pid, name) == (1, "Arsenal")
    assert db.table("player_identity_sources").rows == []
    assert db.table("player_aliases").rows == []


# --- retrieval layer ---


def test_fetch_helpers_shape_and_source_filtering():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="provider-a", external_player_id="33",
        alias="A. Silva", alias_source="provider-a")
    db.table("player_identity_sources").rows.append(
        {"player_id": 7, "source": "provider-b", "external_player_id": "33"})
    scoped = fetch_player_mappings(db, source="provider-a")
    assert scoped == [{"player_id": pid, "source": "provider-a",
                       "external_player_id": "33"}]
    assert len(fetch_player_mappings(db)) == 2
    assert fetch_player_mappings(db, source="PROVIDER-A") == []
    assert fetch_player_mappings(db, source="") == fetch_player_mappings(db)
    assert fetch_player_aliases(db, source="provider-a") == [
        {"player_id": pid, "alias": "A. Silva", "source": "provider-a"}]
    with pytest.raises(TypeError):
        fetch_player_aliases(db, source=39)


def test_fetch_to_resolve_end_to_end():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="provider-a", external_player_id="33",
        alias="A. Silva", alias_source="provider-a")
    assert resolve_player(
        source="provider-a", external_player_id="33",
        alias="A. Silva",
        players=fetch_players(db),
        player_mappings=fetch_player_mappings(db),
        aliases=fetch_player_aliases(db)) == (pid, "Alex Silva")


def test_empty_store_resolves_nothing():
    db = _db()
    assert fetch_players(db) == []
    assert fetch_player_mappings(db) == []
    assert fetch_player_aliases(db) == []
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(name="Alex Silva", players=[])


# --- determinism ---


def test_resolution_is_deterministic():
    db = _db()
    pid, _ = register_player(
        name="Alex Silva", supabase=db,
        source="provider-a", external_player_id="33")
    kwargs = dict(source="provider-a", external_player_id="33")
    first = resolve_player(
        players=fetch_players(db),
        player_mappings=fetch_player_mappings(db), **kwargs)
    second = resolve_player(
        players=list(reversed(fetch_players(db))),
        player_mappings=list(reversed(fetch_player_mappings(db))), **kwargs)
    assert first == second == (pid, "Alex Silva")


# --- 7.4 remediation regression: source alone must not engage mapping ---


def _remediation_fixture():
    """players [{7 John Smith}, {8 Johnny Smith}]; A:123 -> 7; X:John S. -> 7."""
    players = [{"id": 7, "name": "John Smith"},
               {"id": 8, "name": "Johnny Smith"}]
    mappings = [{"source": "A", "external_player_id": "123", "player_id": 7}]
    aliases = [{"alias": "John S.", "source": "X", "player_id": 7}]
    return players, mappings, aliases


def test_remediation_alias_scoped_by_source_resolves():
    """CASE A. Failed against the pre-fix dispatch (spurious Unknown)."""
    players, mappings, aliases = _remediation_fixture()
    assert resolve_player(
        alias="John S.", source="X",
        players=players, player_mappings=mappings,
        aliases=aliases) == (7, "John Smith")


def test_remediation_name_with_source_qualifier_resolves():
    """CASE B. Must not be rejected merely for absent external_player_id."""
    players, mappings, aliases = _remediation_fixture()
    assert resolve_player(
        name="John Smith", source="X",
        players=players, player_mappings=mappings,
        aliases=aliases) == (7, "John Smith")


def test_remediation_id_with_source_qualifier_resolves():
    """CASE C. Canonical ID resolution stays independent of mapping."""
    players, mappings, aliases = _remediation_fixture()
    assert resolve_player(
        player_id=7, source="X",
        players=players, player_mappings=mappings,
        aliases=aliases) == (7, "John Smith")


def test_remediation_source_alone_skips_mapping_path():
    """CASE E. Source without external ID falls through; still Unknown here."""
    players, mappings, aliases = _remediation_fixture()
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(source="X", players=players,
                       player_mappings=mappings, aliases=aliases)


def test_remediation_external_id_without_source_still_unknown():
    """CASE F. Approved partial-reference behavior retained."""
    players, mappings, aliases = _remediation_fixture()
    with pytest.raises(UnknownPlayerIdentityError):
        resolve_player(external_player_id="123", players=players,
                       player_mappings=mappings, aliases=aliases)


def test_remediation_provider_signal_still_exclusive():
    """CASE D. source + external ID resolves through mapping only."""
    players, mappings, aliases = _remediation_fixture()
    assert resolve_player(
        source="A", external_player_id="123",
        players=players, player_mappings=mappings,
        aliases=aliases) == (7, "John Smith")


def test_remediation_multi_signal_agreement_resolves():
    """CASE G (agree): mapping + alias + name converge on player 7."""
    players, mappings, aliases = _remediation_fixture()
    assert resolve_player(
        source="A", external_player_id="123",
        alias="John S.", alias_source="X", name="John Smith",
        players=players, player_mappings=mappings,
        aliases=aliases) == (7, "John Smith")


def test_remediation_multi_signal_disagreement_conflicts():
    """CASE G (disagree): mapping -> 7 but alias -> 8 raises Conflict."""
    players, mappings, _ = _remediation_fixture()
    with pytest.raises(PlayerIdentityConflictError):
        resolve_player(
            source="A", external_player_id="123",
            alias="John S.", alias_source="X", name="John Smith",
            players=players, player_mappings=mappings,
            aliases=[{"alias": "John S.", "source": "X", "player_id": 8}])
