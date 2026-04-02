import pandas as pd
import json
import os

# ---------------------------------------------------------------------

class Ingredient:
    def __init__(self, name, co2_per_kg):
        self.name = name
        self.co2_per_kg = float(co2_per_kg)

class Appliance:
    def __init__(self, name, co2_per_hour):
        self.name = name
        self.co2_per_hour = float(co2_per_hour)

class RecipeStep:
    def __init__(self, name, description, appliance=None):
        self.name = name
        self.description = description
        self.appliance = appliance
        self.inputs = []
        self.time = 0.0

    def add_ingredient(self, ingredient, amount_kg, original_name=""):
        self.inputs.append({'ingredient': ingredient, 'amount': amount_kg, 'original_name': original_name})

    def set_duration(self, time_min):
        self.time = time_min

    def calculate_metrics(self):
        emissions = 0.0
        mass = 0.0
        details = {'ingredients': [], 'appliance': None}
        
        # 食材计算
        for item in self.inputs:
            ing = item['ingredient']
            amt = item['amount']
            orig = item['original_name']
            
            ing_emission = amt * ing.co2_per_kg
            emissions += ing_emission
            mass += amt
            details['ingredients'].append({
                'original': orig,
                'mapped': ing.name,
                'amount': amt,
                'emission': ing_emission
            })
            
        # 能耗计算
        if self.appliance and self.time > 0:
            app_emission = self.appliance.co2_per_hour * (self.time / 60.0)
            emissions += app_emission
            details['appliance'] = {
                'name': self.appliance.name,
                'time_min': self.time,
                'emission': app_emission
            }
        
        return {
            'emissions': emissions, 
            'mass': mass,
            'time': self.time,
            'details': details
        }

class Recipe:
    def __init__(self, name, price):
        self.name = name
        self.price = price
        self.steps = []

    def add_step(self, step):
        self.steps.append(step)

    def evaluate(self, labor_rate_per_min=0.25):
        total = {'emissions': 0.0, 'time': 0.0, 'mass': 0.0}
        breakdown = []
        
        # Straight sum of steps (Sequential Process)
        for step in self.steps:
            m = step.calculate_metrics()
            total['emissions'] += m['emissions']
            total['time'] += m['time']
            total['mass'] += m['mass']
            breakdown.append({
                'step_name': step.name,
                'description': step.description,
                'step_emissions': m['emissions'],
                'details': m['details']
            })
            
        # ================================================
        # Metrics Output
        # ================================================
        # 1. Labor Cost (Sum of all step times in sequential model)
        labor_cost = total['time'] * labor_rate_per_min
        
        # 2. Net Profit
        net_profit = self.price - labor_cost
        
        return {
            'Dish': self.name,
            'Price': self.price,
            'Net_Profit': round(net_profit, 2),
            'Emissions': round(total['emissions'], 3),
            'Labor_Cost': round(labor_cost, 2),
            'Time': round(total['time'], 1),
            'Mass_KG': round(total['mass'], 2),
            'Breakdown': breakdown
        }

# ==========================================
# NEW: 真实数据管理器 (Data Loading Layer)
# ==========================================

class DataManager:
    def __init__(self):
        self.ingredients_db = {} # 字典 {name: IngredientObject}
        self.appliances_db = {}  # 字典 {name: ApplianceObject}
        self.menu_list = []      # 列表 [RecipeObject]

    def load_ingredients(self, filepath):
        """读取 CSV 并通过 Pandas 转换为 Ingredient 对象"""
        if not os.path.exists(filepath):
            print(f"Error: File {filepath} not found.")
            return
            
        df = pd.read_csv(filepath)
        print(f"Loading {len(df)} ingredients...")
        
        for _, row in df.iterrows():
            ing = Ingredient(
                name=row['name'], 
                co2_per_kg=row['co2_per_kg']
            )
            self.ingredients_db[row['name']] = ing

    def load_appliances(self, filepath):
        """读取 CSV 并转换为 Appliance 对象"""
        if not os.path.exists(filepath): return
        
        df = pd.read_csv(filepath)
        print(f"Loading {len(df)} appliances...")
        
        for _, row in df.iterrows():
            app = Appliance(
                name=row['name'], 
                co2_per_hour=row['co2_per_hour']
            )
            self.appliances_db[row['name']] = app

    def build_menu_from_json(self, filepath):
        """读取 JSON 并利用已加载的 DB 构建单向 Recipe"""
        if not os.path.exists(filepath): return
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        print(f"Building {len(data)} recipes...")
        
        for recipe_data in data:
            # 1. 创建菜品对象
            dish = Recipe(recipe_data['name'], recipe_data['price'])
            
            # 2. 遍历 JSON 中的步骤 (Steps)
            for step in recipe_data['steps']:
                # 查找对应的设备对象 (如果找不到，默认 None)
                app_name = step.get('appliance')
                app_obj = self.appliances_db.get(app_name)
                
                if app_name and not app_obj:
                    print(f"Warning: Appliance '{app_name}' not found in DB.")

                # 创建节点
                step_obj_inst = RecipeStep(step['step_name'], step['description'], appliance=app_obj)
                step_obj_inst.set_duration(time_min=step['time_min'])
                
                # 3. 遍历步骤中的食材并添加到节点
                if 'ingredients' in step:
                    for ing_item in step['ingredients']:
                        ing_name = ing_item['name']
                        orig_name = ing_item.get('original_name', ing_name)
                        ing_obj = self.ingredients_db.get(ing_name)
                        
                        if ing_obj:
                            step_obj_inst.add_ingredient(ing_obj, ing_item['amount'], orig_name)
                        else:
                            # Silently ignore warnings for now to reduce clutter, or keep if critical
                            pass
                            # print(f"Warning: Ingredient '{ing_name}' not found in DB.")
                
                dish.add_step(step_obj_inst)
            
            self.menu_list.append(dish)

# ==========================================
# 运行主程序
# ==========================================

from optimization import ParetoAnalyzer

def run_real_world_simulation():
    manager = DataManager()
    
    # 1. 加载基础数据 (请确保 csv 文件在同级目录)
    # 你可以先用 Excel 制作这些 csv，然后另存为 CSV UTF-8 格式
    manager.load_ingredients('db_ingredients.csv')
    manager.load_appliances('db_appliances.csv')
    
    # 2. 构建菜单图模型
    manager.build_menu_from_json('db_recipes.json')
    
    # 3. 输出结果
    print("\n" + "="*40)
    print("       MENU ANALYSIS REPORT       ")
    print("="*40)
    
    results_df = []
    
    for dish in manager.menu_list:
        res = dish.evaluate()
        results_df.append(res)
        
        print(f"\n[Dish]: {res['Dish']}")
        print(f" - Gross Price: ${res['Price']}")
        print(f" - Labor Cost: ${res['Labor_Cost']} ({res['Time']} min)")
        print(f" - Net Profit: ${res['Net_Profit']}")
        print(f" - Total Carbon: {res['Emissions']} kgCO2e")
        print(f" - Total Mass: {res['Mass_KG']} kg")
        
        print("   --- Emissions Breakdown ---")
        for step_data in res['Breakdown']:
            if step_data['step_emissions'] > 0:
                print(f"   [{step_data['step_name']}]: {step_data['description']}")
                print(f"      (Step Total: {round(step_data['step_emissions'], 3)} kgCO2e)")
                
                details = step_data['details']
                for ing in details['ingredients']:
                    print(f"      - {ing['original']} -> [{ing['mapped']}]: {round(ing['emission'], 3)} kgCO2e "
                          f"({ing['amount']} kg)")
                          
                if details['appliance']:
                    app = details['appliance']
                    print(f"      - {app['name']}: {round(app['emission'], 3)} kgCO2e "
                          f"({app['time_min']} min)")

    # 如果你想把结果存回 CSV 用于论文图表：
    # pd.DataFrame(results_df).to_csv('final_results.csv', index=False)
    
    # 4. 运行优化分析 (Pareto Analysis)
    print("\nRunning Multi-Objective Optimization...")
    optimizer = ParetoAnalyzer(manager.menu_list)
    optimizer.print_pareto_report()

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # The data generation lines have been removed to allow using external files.
    # Ensure db_ingredients.csv, db_appliances.csv, and db_recipes.json exist.
    # ------------------------------------------------------------------

    run_real_world_simulation()

8.2	Optimization (optimization.py)
class ParetoAnalyzer:
    def __init__(self, menu_list, labor_rate_per_min=0.25):
        """
        Initialize with a list of Recipe objects.
        """
        self.menu_list = menu_list
        self.labor_rate_per_min = labor_rate_per_min
        self.data = []
        self._extract_data()

    def _extract_data(self):
        """Extract Profit and Carbon metrics for analysis."""
        for dish in self.menu_list:
            metrics = dish.evaluate(labor_rate_per_min=self.labor_rate_per_min)
            self.data.append({
                'name': metrics['Dish'],
                'profit': metrics['Net_Profit'],
                'carbon': metrics['Emissions'],
                'price': metrics['Price'],
                'object': dish
            })

    def find_pareto_frontier(self):
        """
        Identify the Pareto Frontier.
        Objectives: Maximize Profit, Minimize Carbon.
        Returns a list of non-dominated recipe dictionaries.
        """
        population = self.data
        pareto_front = []

        for i, candidate in enumerate(population):
            is_dominated = False
            for j, other in enumerate(population):
                if i == j:
                    continue
                
                # Check if 'other' dominates 'candidate'
                # Condition: other has >= profit AND <= carbon
                # AND strictly better in at least one
                if (other['profit'] >= candidate['profit'] and 
                    other['carbon'] <= candidate['carbon'] and
                    (other['profit'] > candidate['profit'] or other['carbon'] < candidate['carbon'])):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto_front.append(candidate)
        
        # Sort by Profit for display
        pareto_front.sort(key=lambda x: x['profit'])
        return pareto_front

    def print_pareto_report(self):
        frontier = self.find_pareto_frontier()
        
        # Calculate BAU Baseline
        if len(self.data) > 0:
            avg_profit = sum(d['profit'] for d in self.data) / len(self.data)
            avg_carbon = sum(d['carbon'] for d in self.data) / len(self.data)
        else:
            avg_profit, avg_carbon = 0.0, 0.0
            
        print("\n" + "="*70)
        print("          MULTI-OBJECTIVE OPTIMIZATION REPORT          ")
        print(" Objectives: Maximize Profit | Minimize Carbon")
        print("="*70)
        print(f" Dataset 'Business As Usual' Baseline ({len(self.data)} recipes):")
        print(f"   -> Average Profit: ${avg_profit:.2f}")
        print(f"   -> Average Carbon: {avg_carbon:.3f} kgCO2e")
        print("-" * 70)
        print(f"{'Dish Name':<42} | {'Profit':>9} | {'Carbon':>9}")
        print("-" * 70)
        
        for item in frontier:
            print(f"{item['name']:<42} | ${item['profit']:>8.2f} | {item['carbon']:>9.3f}")
        print("-" * 70)
        print(f"Optimal Lineup: {len(frontier)} recipes defining the modern frontier.")

8.3	Dataset Matching (data_converter.py)
import pandas as pd
import json
import os
import ast
import re
import difflib

# Common mappings for Food.com -> Agribalyse
MANUAL_ALIASES = {
    "eggs": "egg, raw",
    "egg": "egg, raw",
    "butter": "butter, salted",
    "sugar": "sugar, white",
    "salt": "salt, white",
    "flour": "wheat flour",
    "all-purpose flour": "wheat flour",
    "milk": "milk, semi-skimmed",
    "water": "water, tap",
    "oil": "sunflower oil",
    "vegetable oil": "sunflower oil",
    "olive oil": "olive oil",
    "pepper": "black pepper",
    "onion": "onion, raw",
    "onions": "onion, raw",
    "garlic": "garlic, raw",
    "cloves": "clove",
    "ground beef": "minced meat, beef, 15% fat, raw",
    "chicken": "chicken, meat, raw",
    "chicken breasts": "chicken, meat, raw",
    "cheese": "emmental/swiss cheese",
    "cheddar cheese": "cheddar",
    "potatoes": "potato, raw",
    "baking powder": "chemical raising agent, baking powder",
}

def clean_ingredient_name(name):
    # Lowercase
    name = str(name).lower()
    # Remove things in parentheses (e.g. "milk (low fat)")
    name = re.sub(r'\(.*?\)', '', name)
    # Remove common irrelevant adjectives
    words_to_remove = [
        "fresh", "chopped", "minced", "diced", "sliced", "large", "small", "medium", 
        "whole", "ground", "dried", "crushed", "shredded", "grated", "canned", 
        "cup", "cups", "teaspoon", "tablespoon", "ounce", "ounces", "lb", "pound"
    ]
    for w in words_to_remove:
        name = name.replace(f" {w} ", " ").replace(f"^{w} ", "").replace(f" {w}$", "")
    
    # Simple plural fix (very naive)
    if name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]
        
    return name.strip()

# Paths
AGRIBALYSE_PATH = 'agribalyse/Agribalyse_Synthese.csv'
RECIPES_PATH = 'db_recipes/RAW_recipes.csv'
UBER_EATS_PATH = 'uber_eats/restaurant-menus.csv'
OUT_INGREDIENTS = 'db_ingredients.csv'
OUT_APPLIANCES = 'db_appliances.csv'
OUT_RECIPES = 'db_recipes.json'
OUT_PRICES = 'db_prices.csv'

def create_appliances_db():
    print("Creating appliances database...")
    appliances = [
        {"name": "Oven", "co2_per_hour": 1.20},
        {"name": "Stove", "co2_per_hour": 0.75},
        {"name": "Microwave", "co2_per_hour": 0.60},
        {"name": "Blender", "co2_per_hour": 0.25},
        {"name": "Toaster", "co2_per_hour": 0.40},
        {"name": "Fridge", "co2_per_hour": 0.05},
        {"name": "Freezer", "co2_per_hour": 0.10},
        {"name": "Prep Table", "co2_per_hour": 0.00},
    ]
    df = pd.DataFrame(appliances)
    df.to_csv(OUT_APPLIANCES, index=False)
    print(f"Saved {len(df)} appliances to {OUT_APPLIANCES}")

def create_ingredients_db():
    print("Creating ingredients database from Agribalyse...")
    if not os.path.exists(AGRIBALYSE_PATH):
        print(f"Error: {AGRIBALYSE_PATH} not found.")
        return None

    try:
        df = pd.read_csv(AGRIBALYSE_PATH, low_memory=False)
    except Exception as e:
        print(f"Error reading Agribalyse: {e}")
        return None

    # Agribalyse columns: 'LCI Name' (English name), 'Changement climatique' (CO2)
    ingredients = []
    
    for _, row in df.iterrows():
        name = row['LCI Name'] if pd.notna(row['LCI Name']) else row['Nom du Produit en Français']
        co2 = row['Changement climatique']
        
        if pd.notna(name) and pd.notna(co2):
            ingredients.append({
                "name": str(name).strip(),
                "co2_per_kg": float(co2)
            })
        
    out_df = pd.DataFrame(ingredients)
    out_df = out_df.drop_duplicates(subset=['name'])
    out_df.to_csv(OUT_INGREDIENTS, index=False)
    print(f"Saved {len(out_df)} ingredients to {OUT_INGREDIENTS}")
    return out_df

def create_prices_db():
    print("Creating prices database from Uber Eats...")
    
    if os.path.exists(OUT_PRICES):
        print(f"Loading existing prices from {OUT_PRICES}...")
        return pd.read_csv(OUT_PRICES)
        
    if not os.path.exists(UBER_EATS_PATH):
        print(f"Error: {UBER_EATS_PATH} not found.")
        return None

    try:
        print("Reading Uber Eats CSV (this might take a few seconds)...")
        # Read relevant columns
        df = pd.read_csv(UBER_EATS_PATH, usecols=['name', 'price'])
    except Exception as e:
        print(f"Error reading Uber Eats: {e}")
        return None
        
    # Clean price: remove ' USD' and convert to float
    df = df.dropna(subset=['price', 'name'])
    df['price'] = df['price'].astype(str).str.replace(' USD', '', regex=False)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df.dropna(subset=['price'])
    
    # Standardize names
    df['name'] = df['name'].astype(str).str.strip().str.lower()
    
    # Group by name and calculate median price
    print("Aggregating prices (median)...")
    price_db = df.groupby('name')['price'].median().reset_index()
    
    # Save
    price_db.to_csv(OUT_PRICES, index=False)
    print(f"Saved {len(price_db)} prices to {OUT_PRICES}")
    return price_db

def process_recipes(ingredients_df):
    print("Processing recipes...")
    if not os.path.exists(RECIPES_PATH):
        print(f"Error: {RECIPES_PATH} not found.")
        return

    # Load Prices
    price_df = create_prices_db()
    if price_df is None:
        print("Cannot process recipes without price mapping.")
        return
        
    price_map = {str(n).strip().lower(): p for n, p in zip(price_df['name'], price_df['price'])}
    price_names_set = set(price_map.keys())

    # Map lower-case name -> Proper LCI Name
    agribalyse_map = {str(name).lower(): name for name in ingredients_df['name'].tolist() if pd.notna(name)}
    agribalyse_names = list(agribalyse_map.keys())
    
    # Load recipes. To be thoroughly exhaustive but efficient, filter to exact name hits first.
    print("Loading Food.com recipes and intersecting with Uber Eats prices...")
    df_recipes = pd.read_csv(RECIPES_PATH)
    df_recipes['norm_name'] = df_recipes['name'].astype(str).str.lower().str.strip()
    df_matched = df_recipes[df_recipes['norm_name'].isin(price_names_set)]
    
    recipes_list = []
    match_cache = {}
    
    print(f"Found {len(df_matched)} recipes intersecting with prices. Checking ingredients...")
    processed_count = 0
    
    for i, row in df_matched.iterrows():
        processed_count += 1
        if processed_count > 1000 and len(recipes_list) >= 50:
            # We want to output around 50 verified active recipes for the demo execution.
            break

        recipe_name = row['name']
        minutes = row['minutes']
        clean_r_name = row['norm_name']
        
        # Proper handling: Skip if no price (already guaranteed by intersection, but fetching it)
        final_price = price_map.get(clean_r_name)
        if final_price is None:
            continue
            
        try:
            ingr_list = ast.literal_eval(row['ingredients'])
        except:
            continue
            
        if not ingr_list:
            continue
            
        recipe_dict = {
            "id": str(row['id']),
            "name": str(recipe_name).title(),
            "price": final_price,
            "price_source": "exact_match", # Strictly using the real price matches from Uber Eats
            "steps": []
        }
        
        step_ingredients = []
        skip_recipe = False
        
        for ing_name in ingr_list:
            clean_name = clean_ingredient_name(ing_name)
            
            # Use dictionary caching to avoid massive repeating difflib
            if clean_name in match_cache:
                final_name = match_cache[clean_name]
            else:
                final_name = None
                
                # 1. Manual Aliases
                if clean_name in MANUAL_ALIASES:
                    target = MANUAL_ALIASES[clean_name]
                    if target.lower() in agribalyse_map:
                        final_name = agribalyse_map[target.lower()]
                
                # 2. Exact Match (Cleaned)
                if not final_name and clean_name in agribalyse_map:
                    final_name = agribalyse_map[clean_name]
                    
                # 3. Fuzzy Match (Cleaned)
                if not final_name:
                    matches = difflib.get_close_matches(clean_name, agribalyse_names, n=1, cutoff=0.6)
                    if matches:
                        final_name = agribalyse_map[matches[0]]
                
                # 4. Token Set Match
                if not final_name:
                    ing_tokens = set(clean_name.split())
                    if len(ing_tokens) > 0:
                        for ag_name in agribalyse_names:
                            ag_tokens = set(ag_name.lower().split())
                            if ing_tokens.issubset(ag_tokens):
                                final_name = agribalyse_map[ag_name]
                                break

                match_cache[clean_name] = final_name

            # Proper handling: strictly skip recipe if we can't legitimately map the ingredient
            if final_name is None:
                skip_recipe = True
                break

            step_ingredients.append({
                "original_name": ing_name,
                "name": final_name, 
                "amount": 0.15 # Assigned default portion size assuming per-person serving
            })

        if skip_recipe:
            continue

        # --- PARSE NATURAL STEPS ---
        try:
            raw_steps = ast.literal_eval(row['steps'])
        except:
            raw_steps = ["Prepare ingredients and cook."]
            
        if not raw_steps:
            raw_steps = ["Prepare ingredients and cook."]
            
        # Distribute total minutes proportionally based on step string length
        total_chars = sum(len(s) for s in raw_steps)
        
        for step_idx, step_text in enumerate(raw_steps):
            step_lower = step_text.lower()
            
            # 1. Determine Appliance
            appliance = "Prep Table" # Default
            if "bake" in step_lower or "oven" in step_lower or "roast" in step_lower:
                appliance = "Oven"
            elif "boil" in step_lower or "simmer" in step_lower or "fry" in step_lower or "skillet" in step_lower:
                appliance = "Stove"
            elif "microwave" in step_lower:
                appliance = "Microwave"
            elif "blend" in step_lower or "puree" in step_lower or "food processor" in step_lower:
                appliance = "Blender"
            elif "toast" in step_lower:
                appliance = "Toaster"
            elif "chill" in step_lower or "refrigerate" in step_lower:
                appliance = "Fridge"
            elif "freeze" in step_lower:
                appliance = "Freezer"

            # 2. Assign Time
            # Use regex to extract time from text if possible, otherwise default to 5
            time_match = re.search(r'(\d+)\s*(to|-)?\s*(\d+)?\s*(minute|min|hr|hour)', step_lower)
            step_time_min = 5
            if time_match:
                val = time_match.group(3) if time_match.group(3) else time_match.group(1)
                try:
                    step_time_min = int(val)
                    if 'hr' in time_match.group(4) or 'hour' in time_match.group(4):
                        step_time_min *= 60
                except:
                    step_time_min = 5
                
            # 3. Assign Ingredients (Simplification: Assign all to the very first step to ensure they are loaded)
            assigned_ingredients = step_ingredients if step_idx == 0 else []

            step_obj = {
                "step_name": f"Step {step_idx + 1}",
                "description": step_text.capitalize(),
                "appliance": appliance,
                "time_min": step_time_min,
                "ingredients": assigned_ingredients
            }
            recipe_dict['steps'].append(step_obj)
        recipes_list.append(recipe_dict)
        
    with open(OUT_RECIPES, 'w') as f:
        json.dump(recipes_list, f, indent=2)
        
    print(f"Successfully saved {len(recipes_list)} purely verified recipes to {OUT_RECIPES}")

def main():
    print("========================================")
    print(" Data Conversion Pipeline")
    print("========================================")
    
    # 1. Create Base Data
    create_appliances_db()
    ingredients_df = create_ingredients_db()
    
    # 2. Process Recipes
    if ingredients_df is not None:
        process_recipes(ingredients_df)
    
    print("\nData conversion complete. Ready for simulation.")

if __name__ == "__main__":
    main()



