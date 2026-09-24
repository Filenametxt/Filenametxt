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

import datetime

def get_contribution_calendar():
    if not TOKEN:
        return None
    url = "https://api.github.com/graphql"
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    data_payload = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data_payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "User-Agent": "Filenametxt-README-Updater",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("data", {}).get("user", {}).get("contributionsCollection", {}).get("contributionCalendar")
    except Exception as e:
        print(f"GraphQL request error: {e}")
        return None

def generate_activity_svg(days_data):
    # days_data: list of (date_str 'YYYY-MM-DD', count)
    width = 820
    height = 240
    pad_left = 50
    pad_right = 30
    pad_top = 60
    pad_bottom = 40
    
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom
    
    counts = [c for _, c in days_data]
    total_period = sum(counts)
    max_count = max(counts) if counts and max(counts) > 0 else 1
    # Ensure a nice ceiling
    y_max = max(max_count, 5)
    
    n = len(days_data)
    points = []
    for i, (d, count) in enumerate(days_data):
        x = pad_left + (i * chart_w / (n - 1 if n > 1 else 1))
        y = pad_top + chart_h - (count / y_max * chart_h)
        points.append((x, y, d, count))
        
    # Build bezier curve path
    if len(points) == 1:
        line_d = f"M {points[0][0]:.1f} {points[0][1]:.1f}"
    else:
        line_d = f"M {points[0][0]:.1f} {points[0][1]:.1f}"
        for i in range(len(points) - 1):
            p0 = points[i - 1] if i > 0 else points[i]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[i + 2] if i + 2 < len(points) else p2
            
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            
            line_d += f" C {cp1x:.1f} {cp1y:.1f}, {cp2x:.1f} {cp2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}"
            
    bottom_y = pad_top + chart_h
    area_d = f"{line_d} L {points[-1][0]:.1f} {bottom_y:.1f} L {points[0][0]:.1f} {bottom_y:.1f} Z"
    
    # Grid lines & Y labels
    grid_svg = ""
    for steps in [0, 0.5, 1.0]:
        val = int(y_max * steps)
        gy = pad_top + chart_h - (steps * chart_h)
        grid_svg += f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" stroke="#21262d" stroke-dasharray="3 3" />\n'
        grid_svg += f'<text x="{pad_left - 10}" y="{gy + 4:.1f}" fill="#8b949e" font-size="11" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" text-anchor="end">{val}</text>\n'
        
    # X labels & points
    x_labels_svg = ""
    step_label = max(1, n // 6)
    for i, (px, py, d, count) in enumerate(points):
        if i % step_label == 0 or i == n - 1:
            try:
                dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                formatted_d = dt.strftime("%d %b")
            except Exception:
                formatted_d = d[-5:]
            x_labels_svg += f'<text x="{px:.1f}" y="{bottom_y + 20}" fill="#8b949e" font-size="11" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" text-anchor="middle">{formatted_d}</text>\n'
            
    points_svg = ""
    for px, py, d, count in points:
        if count > 0:
            points_svg += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#ffffff" stroke="#03d162" stroke-width="2.5" />\n'
        else:
            points_svg += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2" fill="#30363d" />\n'
            
    svg_content = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="activityGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#03d162" stop-opacity="0.38" />
      <stop offset="100%" stop-color="#03d162" stop-opacity="0.0" />
    </linearGradient>
  </defs>

  <!-- Background Card -->
  <rect width="{width}" height="{height}" rx="10" fill="#0D1117" stroke="#30363d" stroke-width="1" />

  <!-- Header -->
  <g transform="translate(25, 32)">
    <path d="M10.5 8a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z M8 1a7 7 0 100 14A7 7 0 008 1zM8 3.5a4.5 4.5 0 110 9 4.5 4.5 0 010-9z" fill="#03d162" transform="translate(0, -12) scale(1.1)" />
    <text x="25" y="0" fill="#ffffff" font-size="15" font-weight="600" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">Commit Activity (Last 30 Days)</text>
    <text x="{width - 55}" y="0" fill="#8b949e" font-size="13" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" text-anchor="end">Total: <tspan fill="#03d162" font-weight="bold">{total_period}</tspan> commits</text>
  </g>

  <!-- Grid & Axes -->
  {grid_svg}
  {x_labels_svg}

  <!-- Area Fill & Line Chart -->
  <path d="{area_d}" fill="url(#activityGrad)" />
  <path d="{line_d}" fill="none" stroke="#03d162" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" />

  <!-- Data Points -->
  {points_svg}
</svg>"""
    return svg_content

def update_readme():
    repos = get_repositories()
    
    public_repos_data = []
    private_repos_data = []
    
    for repo in repos:
        if repo.get('fork'):
            continue
            
        name = repo.get('name')
        description = repo.get('description') or "No description provided."
        is_private = repo.get('private', False)
        pushed_at = repo.get('pushed_at', '')
        
        # Ottieni i commit dell'utente per questo repository
        commits = get_commit_count(name)
        
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

    # Generazione dei dati di commit per il grafico dell'attività (ultimi 30 giorni)
    days_data = []
    calendar = get_contribution_calendar()
    if calendar and "weeks" in calendar:
        all_days = []
        for week in calendar["weeks"]:
            for day in week.get("contributionDays", []):
                all_days.append((day["date"], day["contributionCount"]))
        # Prendi gli ultimi 30 giorni
        days_data = all_days[-30:] if len(all_days) >= 30 else all_days
    else:
        today = datetime.date.today()
        for i in range(29, -1, -1):
            d_str = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            days_data.append((d_str, 0))

    # Genera e scrivi il file SVG dell'attività
    svg_activity = generate_activity_svg(days_data)
    with open("commit_activity.svg", "w", encoding="utf-8") as f:
        f.write(svg_activity)

    # Template del README.md con solo il grafico dei commit di GitHub e i progetti
    readme_template = f"""## 📊 GitHub Activity
![Commit Activity](commit_activity.svg)

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

    # Scrittura del file README.md
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_template)
    
    print("README.md and commit_activity.svg updated successfully!")

if __name__ == "__main__":
    update_readme()
