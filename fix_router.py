with open('football_api_client.py', 'r') as f:
    lines = f.readlines()

new_lines = []
in_init = False
for line in lines:
    if 'def __init__(self):' in line:
        in_init = True
        new_lines.append(line)
        continue

    if in_init:
        if 'self.stats_provider = None' in line:
            new_lines.append(line)
            # Add keys and logic
            new_lines.append("        rapid_key = os.environ.get('RAPIDAPI_KEY')\n")
            new_lines.append("        fd_key = os.environ.get('FOOTBALL_DATA_API_KEY')\n")
            new_lines.append("        sr_key = os.environ.get('SPORTRADAR_API_KEY')\n")
            new_lines.append("        stats_key = os.environ.get('THESTATSAPI_KEY')\n")
            new_lines.append("\n")
            new_lines.append("        # Priority ordering: fd_key, sr_key, then rapid_key based providers\n")
            new_lines.append("        if fd_key:\n")
            new_lines.append("            self.providers.append(FootballDataOrgProvider(fd_key))\n")
            new_lines.append('            self.circuit_breaker["FootballDataOrgProvider"] = {"status": "healthy", "last_failure": None}\n')
            new_lines.append("        if sr_key:\n")
            new_lines.append("            self.providers.append(SportradarProvider(sr_key))\n")
            new_lines.append('            self.circuit_breaker["SportradarProvider"] = {"status": "healthy", "last_failure": None}\n')
            new_lines.append("        if rapid_key:\n")
            new_lines.append("            self.providers.append(ThreeSixFiveScoresProvider(rapid_key))\n")
            new_lines.append("            self.providers.append(RapidAPIProvider(rapid_key))\n")
            new_lines.append('            self.circuit_breaker["ThreeSixFiveScoresProvider"] = {"status": "healthy", "last_failure": None}\n')
            new_lines.append('            self.circuit_breaker["RapidAPIProvider"] = {"status": "healthy", "last_failure": None}\n')
            new_lines.append("        if stats_key:\n")
            new_lines.append("            self.stats_provider = TheStatsAPIProvider(stats_key)\n")
            in_init = False # Skip the rest of the old init
            continue
        elif 'self.circuit_breaker = {}' in line or 'self.POPULAR_LEAGUES' in line:
            new_lines.append(line)
            continue
        elif line.strip().startswith('if fd_key:') or line.strip().startswith('if sr_key:') or line.strip().startswith('if rapid_key:'):
            continue # Skip old logic
        elif 'self.stats_provider = TheStatsAPIProvider' in line:
            continue
        elif 'rapid_key =' in line or 'fd_key =' in line or 'sr_key =' in line:
            continue

    if not in_init or line.strip() == '':
        new_lines.append(line)

# Let's just do a clean replacement of the __init__ method
import re
content = "".join(lines)
init_pattern = r'def __init__\(self\):.*?if stats_key:\s+self\.stats_provider = TheStatsAPIProvider\(stats_key\)'
new_init = """def __init__(self):
        self.providers = []
        self.stats_provider = None
        self.circuit_breaker = {} # {provider_name: {"status": "healthy", "last_failure": None}}
        self.POPULAR_LEAGUES = {
            47: "Premier League", 87: "La Liga", 54: "Bundesliga", 55: "Serie A",
            53: "Ligue 1", 42: "Champions League", 73: "Europa League"
        }

        # Load keys strictly from environment
        rapid_key = os.environ.get('RAPIDAPI_KEY')
        fd_key = os.environ.get('FOOTBALL_DATA_API_KEY')
        sr_key = os.environ.get('SPORTRADAR_API_KEY')
        stats_key = os.environ.get('THESTATSAPI_KEY')

        # We prefer Football-Data.org (fd_key) or Sportradar (sr_key) over RapidAPI (rapid_key)
        # because RapidAPI quota is often exceeded.
        if fd_key:
            self.providers.append(FootballDataOrgProvider(fd_key))
            self.circuit_breaker["FootballDataOrgProvider"] = {"status": "healthy", "last_failure": None}
        if sr_key:
            self.providers.append(SportradarProvider(sr_key))
            self.circuit_breaker["SportradarProvider"] = {"status": "healthy", "last_failure": None}
        if rapid_key:
            # RapidAPI providers are last resort
            self.providers.append(ThreeSixFiveScoresProvider(rapid_key))
            self.providers.append(RapidAPIProvider(rapid_key))
            self.circuit_breaker["ThreeSixFiveScoresProvider"] = {"status": "healthy", "last_failure": None}
            self.circuit_breaker["RapidAPIProvider"] = {"status": "healthy", "last_failure": None}
        if stats_key:
            self.stats_provider = TheStatsAPIProvider(stats_key)"""

content = re.sub(init_pattern, new_init, content, flags=re.DOTALL)
with open('football_api_client.py', 'w') as f:
    f.write(content)
