import time
import requests as rq
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from datetime import datetime
import os
from dotenv import load_dotenv

#Load environment variables
load_dotenv()

now = datetime.now()

current_day = now.day
current_month = now.strftime("%b")
current_year = now.year
day_of_week = now.strftime('%A')

date = f"{day_of_week}, {current_month} {current_day}, {current_year}"


url = "https://netnutrition.cbord.com/nn-prod/Duke"

with open("data.db", "w", encoding="utf-8") as file:
    with sync_playwright() as p:

        # Launch Edge using the Chromium engine
        browser = p.chromium.launch(channel="msedge", headless=False)  # Set headless=True for background execution
        page = browser.new_page()

        # Navigate to a URL
        page.goto(url)
        time.sleep(3)

        # Close the popup (e.g., clicking the close button in the popup)
        page.locator("button.close-popup").click()  # Adjust selector

        # Get the rendered page content
        html_content = page.content()
        #Parse HTML Content
        soup = BeautifulSoup(html_content, "html.parser")

        time.sleep(3)

        #Section with all separate event pages
        page.click("div#unitsPanel a:text('Marketplace')")

        #print(link)
        time.sleep(3)

         # Get the rendered page content
        html_content = page.content()
        #Parse HTML Content
        soup = BeautifulSoup(html_content, "html.parser")

        page.click(f"div:text({date}) a:text('Dinner')")
        
        time.sleep(3)
        
        index = 0
        events = []
        for event in content.find_all("li", class_="list-group-item"):  
            if(index==0):
                index+=1
                continue
            event_page = event.find("h3",class_="media-heading header-cg--h4").find("a").get('href')
            name = event.find("h3",class_="media-heading header-cg--h4").get_text()
            file.write("Name of Event: "+name + "\n")
            page.goto("https://duke.campusgroups.com"+event_page)
            time.sleep(3)
            contents = page.content()
            soup = BeautifulSoup(contents, "html.parser")
            description = " ".join((soup.find("div",id="event_details").find("div",class_="card-block").get_text()).split())
            file.write("Description: " + description + "\n")
            location = soup.find("div",id="event_main_card").find("div",attrs={"style":"display: inline-block; margin-left: 3px; width: calc(100% - 50px);"}).find_all("p")[0].get_text()
            _time = soup.find("div",id="event_main_card").find("div",attrs={"style":"display: inline-block; margin-left: 3px;"}).find_all("p")[1].get_text()[0:-11]
            file.write("Location: "+location + "\n")
            file.write("Time: "+ _time+ "\n"+"\n")
            time.sleep(3)
            index+=1

        # Close the browser
        browser.close()
