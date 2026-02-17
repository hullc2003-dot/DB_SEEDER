import requests
from bs4 import BeautifulSoup

def run_learning_pipeline(url):
    # Step 6: Retrieve all text/HTML
    response = requests.get(url, timeout=10)
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    
    # Clean up script/style tags to get pure text schema
    for script in soup(["script", "style"]):
        script.extract()
    
    plain_text = soup.get_text(separator=' ')
    word_count = len(plain_text.split())
    
    # Step 7: Log status (Orchestrator handles the "holding" of this)
    # Step 9: Maintaining original schema by passing the soup object/html
    # Step 10: Logic returns to orchestrator signaling handoff is ready
    return {
        "status_msg": "text retrieved",
        "word_count": word_count,
        "raw_text": plain_text,
        "html": html
    }
