import re
from playwright.sync_api import Playwright, sync_playwright, expect
from parsel import Selector
import pandas as pd


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    total_marques_names:list=[]
    total_modeles_names :list=[]
    motorisation_true_names: list=[]
    try:
        page = context.new_page()
        page.goto("https://www.cartec.ma/")
        page.wait_for_load_state("domcontentloaded")
        page_source = page.locator("html").inner_html()
        selector= Selector(page_source)
        marques = [marqua.attrib['value'] for marqua in selector.css("#manufacturer-select > option")]
        marques_names = selector.css("#manufacturer-select > option ::text").getall()
        marques_true_names=[]
        for marque in marques_names[1:]:
            page_source = page.locator("html").inner_html()
            selector= Selector(page_source)
            marque=str(marque).replace("\n","").replace("            ","").replace("    ","")
            marques_true_names.append(marque)
        print(marques_true_names)
        #total_marques_names= []
        #total_modeles_names =[]
        #motorisation_true_names=[]
        for marque in marques[1:]:
            #print(marque)
            
            print(marques_true_names[marques.index(marque)-1])
            page.locator("#manufacturer-select").select_option(str(marque))
            page.wait_for_timeout(200)
            page_source = page.locator("html").inner_html()
            selector= Selector(page_source)
            modeles_count=len(page.query_selector_all("#model-select > option"))
            print(modeles_count)
            #for i in range(modeles_count):
                #total_marques_names.append(marques_true_names[marques.index(marque)-1])
            modeles= [modele.attrib['value'] for modele in selector.css("#model-select > option")]
            modeles_names = selector.css("#model-select > option ::text").getall()[1:]
            print("Modeles...")
            #print(len(modeles_names))
            print(modeles_names)


            modeles_true_names=[]
        
                
            #total_modeles_names = []
            for modele in modeles[1:]:
                try:
                    modele_name=str(modeles_names[modeles.index(modele)]).replace("\n","").replace("            ","").replace("    ","")
                    modeles_true_names.append(modele_name)
                    print(modele_name)
                    #page.locator("#model-select").click()
                    page.locator("#model-select").select_option(str(modele))
                    page.wait_for_timeout(200)
                    page_source = page.locator("html").inner_html()
                    selector= Selector(page_source)
                    #vehicle_count=len(page.query_selector_all("#vehicle-select > option"))
                    motorisation_names = selector.css("#vehicle-select  option ::text").getall()[1:]
                    motorisations_options = [moto.attrib['value'] for moto in selector.css("#vehicle-select  option")]
                    for i in range(1,len(motorisation_names)):
                        total_modeles_names.append(modeles_true_names[modeles.index(modele)-1])
                        total_marques_names.append(marques_true_names[marques.index(marque)-1])
                        motorisations=str(motorisation_names[i]).replace("\n","").replace("            ","").replace("    ","")
                        print(motorisations)
                        motorisation_true_names.append(motorisations)
                        page.locator("#vehicle-select").select_option(str(motorisations_options[i]))
                        page.locator("#content  section  div.vehicle-selector.vs_f  div.vehicle-selector__button  a").click()
                        f = input()
                    print(f"motorisation length:\t {len(motorisation_true_names)}")
                    #motorisation_true_names=[]
                    #for motorisation in motorisation_names[1:]
                except:
                    continue
                    
        print("total_marques length:\t",len(total_marques_names))
        print("total_modeles length:\t",len(total_modeles_names))
        p
    except Exception as e :
        print(e)
        pass
    finally:
        print("total_marques length:\t",len(total_marques_names))
        print("total_modeles length:\t",len(total_modeles_names))
        print("total_motorisation length:\t",len(motorisation_true_names))

   # page.locator("#manufacturer-select").select_option("3854")
   # page.locator("#model-select").select_option("36454")
    #page.locator("#vehicle-select").select_option("119512")

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
