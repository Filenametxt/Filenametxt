import os
import re
import urllib.request
import urllib.parse
import json

# GitHub Configuration
USERNAME = "Filenametxt"
TOKEN = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")

def make_request(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "Filenametxt-README-Updater")
    if TOKEN:
        req.add_header("Authorization", f"token {TOKEN}")
    try:
        with urllib.request.urlopen(req) as response:
            return response.read(), response.headers
    except Exception as e:
        print(f"Error during request to {url}: {e}")
        return None, None

def get_repositories():
    repos = []
    page = 1
    
    if TOKEN:
        base_url = "https://api.github.com/user/repos?type=owner&per_page=100"
    else:
        print("WARNING: No token provided (GH_PAT or GITHUB_TOKEN). Only public repositories will be shown.")
        base_url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100"

    while True:
        url = f"{base_url}&page={page}"
        data, headers = make_request(url)
        if not data:
            break
        try:
            page_repos = json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error parsing repositories JSON: {e}")
            break
            
        if not page_repos or not isinstance(page_repos, list):
            break
            
        repos.extend(page_repos)
        if len(page_repos) < 100:
            break
        page += 1
        
    return repos

def get_commit_count(repo_name):
    url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits?author={USERNAME}&per_page=1"
    data, headers = make_request(url)
    if not data:
        return 0
    
    link_header = headers.get("Link")
    if link_header:
        match = re.search(r'page=(\d+)>; rel="last"', link_header)
        if match:
            return int(match.group(1))
            
    try:
        commits = json.loads(data.decode('utf-8'))
        return len(commits) if isinstance(commits, list) else 0
    except Exception:
        return 0

def get_total_issues():
    # Cerca tutte le issue nei repository dell'utente (pubbliche e private)
    query = urllib.parse.quote(f"user:{USERNAME} type:issue")
    url = f"https://api.github.com/search/issues?q={query}"
    data, headers = make_request(url)
    if not data:
        return 0
    try:
        result = json.loads(data.decode('utf-8'))
        return result.get("total_count", 0)
    except Exception as e:
        print(f"Error calculating issues: {e}")
        return 0

def get_total_prs():
    # Cerca tutte le PR create dall'utente (pubbliche e private)
    query = urllib.parse.quote(f"author:{USERNAME} type:pr")
    url = f"https://api.github.com/search/issues?q={query}"
    data, headers = make_request(url)
    if not data:
        return 0
    try:
        result = json.loads(data.decode('utf-8'))
        return result.get("total_count", 0)
    except Exception as e:
        print(f"Error calculating PRs: {e}")
        return 0

def get_contributed_to():
    # Cerca PR/Issue create dall'utente in repository non di sua proprietà
    query = urllib.parse.quote(f"author:{USERNAME} -user:{USERNAME}")
    url = f"https://api.github.com/search/issues?q={query}"
    data, headers = make_request(url)
    if not data:
        return 0
    try:
        result = json.loads(data.decode('utf-8'))
        repos = set()
        for item in result.get("items", []):
            repo_url = item.get("repository_url", "")
            if repo_url:
                repos.add(repo_url)
        return len(repos)
    except Exception as e:
        print(f"Error calculating contributions: {e}")
        return 0

def get_followers():
    url = f"https://api.github.com/users/{USERNAME}"
    data, headers = make_request(url)
    if not data:
        return 0
    try:
        result = json.loads(data.decode('utf-8'))
        return result.get("followers", 0)
    except Exception as e:
        print(f"Error calculating followers: {e}")
        return 0

# Formule per il calcolo del rank sul modello di github-readme-stats
def exponential_cdf(x):
    return 1 - (2 ** -x)

def log_normal_cdf(x):
    return x / (1 + x)

def calculate_rank(commits, prs, issues, stars, followers):
    COMMITS_MEDIAN = 1000  # Usando include_all_commits = True
    COMMITS_WEIGHT = 2
    PRS_MEDIAN = 50
    PRS_WEIGHT = 3
    ISSUES_MEDIAN = 25
    ISSUES_WEIGHT = 1
    REVIEWS_MEDIAN = 2
    REVIEWS_WEIGHT = 1
    STARS_MEDIAN = 50
    STARS_WEIGHT = 4
    FOLLOWERS_MEDIAN = 10
    FOLLOWERS_WEIGHT = 1

    TOTAL_WEIGHT = (COMMITS_WEIGHT + PRS_WEIGHT + ISSUES_WEIGHT + 
                    REVIEWS_WEIGHT + STARS_WEIGHT + FOLLOWERS_WEIGHT)

    # Assumiamo reviews = 0 per semplicità
    reviews = 0

    rank = 1 - (
        COMMITS_WEIGHT * exponential_cdf(commits / COMMITS_MEDIAN) +
        PRS_WEIGHT * exponential_cdf(prs / PRS_MEDIAN) +
        ISSUES_WEIGHT * exponential_cdf(issues / ISSUES_MEDIAN) +
        REVIEWS_WEIGHT * exponential_cdf(reviews / REVIEWS_MEDIAN) +
        STARS_WEIGHT * log_normal_cdf(stars / STARS_MEDIAN) +
        FOLLOWERS_WEIGHT * log_normal_cdf(followers / FOLLOWERS_MEDIAN)
    ) / TOTAL_WEIGHT

    percentile = rank * 100
    
    THRESHOLDS = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    LEVELS = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    
    level = "C"
    for t, lvl in zip(THRESHOLDS, LEVELS):
        if percentile <= t:
            level = lvl
            break
            
    return level, percentile

def update_readme():
    repos = get_repositories()
    total_issues = get_total_issues()
    total_prs = get_total_prs()
    contributed_to = get_contributed_to()
    followers = get_followers()
    
    public_repos_data = []
    private_repos_data = []
    total_commits = 0
    total_stars = 0
    
    for repo in repos:
        if repo.get('fork'):
            continue
            
        name = repo.get('name')
        description = repo.get('description') or "No description provided."
        is_private = repo.get('private', False)
        pushed_at = repo.get('pushed_at', '')
        stars = repo.get('stargazers_count', 0)
        total_stars += stars
        
        # Ottieni i commit dell'utente per questo repository
        commits = get_commit_count(name)
        total_commits += commits
        
        repo_info = {
            'name': name,
            'description': description,
            'commits': commits,
            'pushed_at': pushed_at,
            'url': repo.get('html_url')
        }
        
        if is_private:
            private_repos_data.append(repo_info)
        else:
            public_repos_data.append(repo_info)
            
    # Ordina i repository pubblici per pushed_at decrescente e prendi i primi 3
    public_repos_data.sort(key=lambda x: x.get('pushed_at') or '', reverse=True)
    top_3_public = public_repos_data[:3]
    public_projects = []
    for r in top_3_public:
        public_projects.append(f"- 🌐 [{r['name']}]({r['url']}) — *{r['description']}* ({r['commits']} commits)")
        
    # Ordina i repository privati per pushed_at decrescente e prendi i primi 3
    private_repos_data.sort(key=lambda x: x.get('pushed_at') or '', reverse=True)
    top_3_private = private_repos_data[:3]
    private_projects = []
    for r in top_3_private:
        private_projects.append(f"- 🔒 **{r['name']}** ({r['commits']} commits)")
        
    # Formattazione delle liste
    if public_projects:
        public_list_str = "\n".join(public_projects)
    else:
        public_list_str = "*No original public projects found.*"
        
    if private_projects:
        private_list_str = "\n".join(private_projects)
    elif not TOKEN:
        private_list_str = "*[Configure a GH_PAT token to view private projects]*"
    else:
        private_list_str = "*No private projects found.*"
        
    # Calcolo del rank e della percentuale
    rank_level, percentile = calculate_rank(
        commits=total_commits,
        prs=total_prs,
        issues=total_issues,
        stars=total_stars,
        followers=followers
    )
    
    # Calcolo dello scostamento del cerchio grafico (stroke-dashoffset)
    # Circonferenza = 2 * PI * R = 2 * 3.14159 * 40 = 251.2
    stroke_offset = (percentile / 100) * 251.2
    
    # Template del file SVG per visualizzare le statistiche reali comprese quelle private
    svg_template = f"""<svg width="495" height="195" viewBox="0 0 495 195" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{ font: bold 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .label {{ font: 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .value {{ font: bold 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d866; }}
    .rank-text {{ font: bold 36px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d866; text-anchor: middle; dominant-baseline: middle; }}
    .rank-circle {{ stroke: #fe428e; stroke-width: 4; fill: none; }}
    .rank-circle-bg {{ stroke: #fe428e; stroke-width: 4; stroke-opacity: 0.15; fill: none; }}
  </style>
  
  <rect x="0.5" y="0.5" width="494" height="194" rx="6" fill="#141321" stroke="#ffffff" />
  
  <text x="25" y="35" class="title">Fabio's GitHub Stats</text>
  
  <!-- Stats Groups -->
  <g transform="translate(25, 50)">
    <!-- Stars -->
    <g transform="translate(0, 15)">
      <path d="M8 .25a.75.75 0 00-1.22 0L4.85 4.1 1.05 4.65a.75.75 0 00-.42 1.28l2.75 2.68-.65 3.78a.75.75 0 001.09.79l3.4-1.78 3.4 1.78a.75.75 0 001.09-.79l-.65-3.78 2.75-2.68a.75.75 0 00-.42-1.28l-3.8-.55L8 .25z" fill="#fe428e" transform="translate(0, -1)" />
      <text x="25" y="10" class="label">Total Stars:</text>
      <text x="170" y="10" class="value">{total_stars}</text>
    </g>
    
    <!-- Commits -->
    <g transform="translate(0, 40)">
      <path d="M10.5 8a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z M8 1a7 7 0 100 14A7 7 0 008 1zM8 3.5a4.5 4.5 0 110 9 4.5 4.5 0 010-9z" fill="#fe428e" transform="scale(0.9) translate(0, -1)" />
      <text x="25" y="10" class="label">Total Commits:</text>
      <text x="170" y="10" class="value">{total_commits}</text>
    </g>
    
    <!-- PRs -->
    <g transform="translate(0, 65)">
      <path d="M5 3.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm0 2.122a2.25 2.25 0 10-1.5 0v5.256a2.251 2.251 0 101.5 0V5.372zm8-.5a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM11.5 7a2.25 2.25 0 100 4.5 2.25 2.25 0 000-4.5zM5 11.5a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm8 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" fill="#fe428e" transform="scale(0.9) translate(0, -1)" />
      <text x="25" y="10" class="label">Total PRs:</text>
      <text x="170" y="10" class="value">{total_prs}</text>
    </g>
    
    <!-- Issues -->
    <g transform="translate(0, 90)">
      <path d="M8 15A7 7 0 118 1a7 7 0 010 14zm0-1A6 6 0 108 2a6 6 0 000 12zM7.25 5h1.5v4.5h-1.5V5zm0 6h1.5v1.5h-1.5V11z" fill="#fe428e" transform="scale(0.9) translate(0, -1)" />
      <text x="25" y="10" class="label">Total Issues:</text>
      <text x="170" y="10" class="value">{total_issues}</text>
    </g>
    
    <!-- Contributed to -->
    <g transform="translate(0, 115)">
      <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM4.5 12.25a.25.25 0 00-.25.25v.25h8v-.25a.25.25 0 00-.25-.25h-7.5z" fill="#fe428e" transform="scale(0.9) translate(0, -1)" />
      <text x="25" y="10" class="label">Contributed to:</text>
      <text x="170" y="10" class="value">{contributed_to}</text>
    </g>
  </g>
  
  <!-- Rank Circle Graphic -->
  <g transform="translate(390, 115)">
    <circle cx="0" cy="0" r="40" class="rank-circle-bg" />
    <circle cx="0" cy="0" r="40" class="rank-circle" stroke-dasharray="251.2" stroke-dashoffset="{stroke_offset}" transform="rotate(-90)" />
    <text x="0" y="0" class="rank-text" dominant-baseline="central" alignment-baseline="central" text-anchor="middle">{rank_level}</text>
  </g>
</svg>
"""

    # Template del README.md con confronto side-by-side delle card
    readme_template = f"""## 📊 GitHub Activity
![Activity Graph](https://github-readme-activity-graph.vercel.app/graph?username={USERNAME}&bg_color=0D1117&color=ffffff&line=03d162&point=ffffff&area=true&hide_border=true)

<p align="center">
  <table>
    <tr>
      <td align="center"><b>Public Stats Only (Vercel)</b></td>
      <td align="center"><b>Total Stats: Public + Private (Generated SVG)</b></td>
    </tr>
    <tr>
      <td><img src="https://github-stats-extended.vercel.app/api?username={USERNAME}&show_icons=true&theme=radical" width="430" alt="Public Stats Only" /></td>
      <td><img src="github_stats.svg" width="430" alt="Total Stats (Public + Private)" /></td>
    </tr>
  </table>
</p>

---

## 📁 My Projects
Here is the list of projects I am working on:

### 🌐 Public Projects (Top 3 Recent)
{public_list_str}

### 🔒 Private Projects (Top 3 Recent)
{private_list_str}

---

*This README updates automatically via GitHub Actions.*
"""
    
    # Scrittura del file github_stats.svg
    with open("github_stats.svg", "w", encoding="utf-8") as f:
        f.write(svg_template)

    # Scrittura del file README.md
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_template)
    
    print("README.md and github_stats.svg updated successfully!")

if __name__ == "__main__":
    update_readme()
