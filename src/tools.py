import ollama, subprocess, os

def clip_contents(result, limit = 8000):
    text = str(result)
    if len(text) > limit:
        return text[:limit] + "\n... [truncated]"

    return text

def web_search(query: str, max_results = 3):
    """
    Performs a web search

    Args:
      query: The query to search for
      max_results: The maximum number of results to return (default: 3)

    Returns:
      WebSearchResponse with the search results
    """
    result = ollama.web_search(query, max_results)
    return clip_contents(result)

def web_fetch(url: str):
    """
    Fetches the content of a web page for the provided URL.

    Args:
      url: The URL to fetch

    Returns:
      WebFetchResponse with the fetched result
    """
    return clip_contents(ollama.web_fetch(url))

def run_application(name: str):
    """
    Launch an installed Linux application by its exact desktop-entry filename.

    Searches the user's local applications directory first, then the system
    applications directory, and launches the matching .desktop entry with gio.

    Args:
        name: Exact .desktop filename, such as "firefox.desktop". This is the
            launcher filename, not necessarily the app's visible name from its
            Name= field.

    Returns:
        A message indicating whether a matching entry was found and launched.
    """

    local_apps = os.path.expanduser("~/.local/share/applications/")
    global_apps = "/usr/share/applications/"

    entry = None

    if os.path.exists(os.path.join(local_apps, name)):
        entry = os.path.join(local_apps, name)
    elif os.path.exists(os.path.join(global_apps, name)):
        entry = os.path.join(global_apps, name)
    else:
        return "No .desktop entry found"
    
    subprocess.Popen(["gio", "launch", entry])
    return f"{entry} was launched sucessfully"

def find_applications(keyword: str):
    """
    Find desktop application launchers whose filenames match a keyword.

    Args:
        keyword: Text to match against launcher filenames.

    Returns:
        Matching .desktop filenames (not full paths).
    """

    local_apps = os.path.expanduser("~/.local/share/applications/")
    global_apps = "/usr/share/applications/"

    matches = []

    for f in os.listdir(local_apps):
        if f.casefold().endswith(".desktop") and keyword in f.casefold():
            matches.append(f)

    for f in os.listdir(global_apps):
        if f.casefold().endswith(".desktop") and keyword in f.casefold():
            matches.append(f)

    return sorted(set(matches), key=str.casefold)

def get_all_applications():
    """
    Return names of all user's .desktop files installed on the system
    """

    local_apps = os.path.expanduser("~/.local/share/applications/")
    global_apps = "/usr/share/applications/"

    matches = []

    for f in os.listdir(local_apps):  matches.append(f)
    for f in os.listdir(global_apps): matches.append(f)

    return sorted(set(matches), key=str.casefold)