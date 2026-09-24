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

    # Template del README.md con solo il grafico dei commit di GitHub e i progetti
    readme_template = f"""## 📊 GitHub Activity
![Activity Graph](https://github-readme-activity-graph.vercel.app/graph?username={USERNAME}&bg_color=0D1117&color=ffffff&line=03d162&point=ffffff&area=true&hide_border=true)

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
    
    print("README.md updated successfully!")

if __name__ == "__main__":
    update_readme()
