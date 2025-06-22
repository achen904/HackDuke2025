
// --- Interfaces ---
interface UserGoals {
  dietaryRestrictions: string[];
  otherDietaryNotes: string;
  primaryGoal: 'weightLoss' | 'weightGain' | 'muscleGain' | 'maintainWeight' | 'healthyEating' | '';
  specificGoals: string;
  mealsConsumed: {
    breakfast: boolean;
    lunch: boolean;
    dinner: boolean;
    snacks: boolean;
  };
}

interface MealItem {
  name: string;
  calories?: number;
  protein?: number;
  description?: string;
}

interface Meal {
  restaurant: string;
  items: MealItem[];
}

interface DailyMealPlan {
  dayName?: string; // e.g., "Monday" or "Today's Plan"
  breakfast: Meal | null;
  lunch: Meal | null;
  dinner: Meal | null;
  snacks?: Meal | null;
}

// --- App State ---
let currentPage: 'home' | 'goalInput' | 'mealPlan' = 'home';
let userGoals: UserGoals = {
  dietaryRestrictions: [],
  otherDietaryNotes: '',
  primaryGoal: '',
  specificGoals: '',
  mealsConsumed: { breakfast: true, lunch: true, dinner: true, snacks: false },
};
let mealPlan: DailyMealPlan | null = null;
let isLoading = false;
let errorMessage = '';

// --- DOM Elements ---
const root = document.getElementById('root')!;

// --- Render Functions ---

function renderApp() {
  if (!root) return;
  root.innerHTML = ''; // Clear previous content

  const headerDiv = document.createElement('div');
  headerDiv.className = 'header';
  headerDiv.innerHTML = `
    <svg class="logo" viewBox="-100 0 125 60" style="enable-background:new -100 0 125 60;" xml:space="preserve" width="100px" height="48px">
      <style type="text/css"> .st0{fill:#FFFFFF;} </style>
      <g>
        <path class="st0" d="M-92.9,56.8c-1.7,0-2.6-1.1-2.6-3v-4h1v4c0,1.3,0.5,2,1.6,2s1.6-0.7,1.6-1.9v-4h1v4 C-90.3,55.8-91.2,56.8-92.9,56.8"/>
        <path class="st0" d="M-77.5,56.7l-2.7-4.3c-0.2-0.3-0.4-0.7-0.5-0.8c0,0.3,0,1.2,0,1.6v3.6h-1v-6.9h1.1l2.6,4.2 c0.2,0.3,0.5,0.8,0.6,1c0-0.3,0-1.2,0-1.6V50h1v6.9h-1.1"/>
        <rect x="-67.8" y="49.9" class="st0" width="1" height="6.9"/>
        <path class="st0" d="M-55.2,56.7h-1.1l-2.4-6.9h1.1l1.4,4.4c0.1,0.4,0.3,1,0.4,1.3c0.1-0.2,0.3-0.9,0.4-1.3l1.4-4.4h1.1L-55.2,56.7"/>
        <polyline class="st0" points="-44.7,56.7 -44.7,49.9 -40.3,49.9 -40.3,50.9 -43.6,50.9 -43.6,52.6 -41.7,52.6 -41.7,53.6 -43.6,53.6 -43.6,55.7 -40.1,55.7 -40.1,56.7 -44.7,56.7"/>
        <path class="st0" d="M-28.2,54l1.4,2.8h-1.1l-1.4-2.7h-1.6v2.7h-1v-6.9h3c1.2,0,2.2,0.6,2.2,2.1C-26.6,53.1-27.2,53.8-28.2,54 M-28.9,50.9h-2v2.2h2c0.7,0,1.2-0.4,1.2-1.1S-28.2,50.9-28.9,50.9z"/>
        <path class="st0" d="M-16.2,56.8c-1,0-1.9-0.4-2.4-1.1l0.7-0.7c0.5,0.5,1.1,0.8,1.8,0.8c1,0,1.4-0.3,1.4-1c0-0.5-0.4-0.8-1.6-1.1 c-1.5-0.4-2.1-0.8-2.1-2s1-1.9,2.3-1.9c0.9,0,1.6,0.3,2.2,0.9l-0.7,0.7c-0.4-0.4-0.9-0.7-1.6-0.7c-0.8,0-1.2,0.4-1.2,0.9 s0.3,0.7,1.5,1.1c1.4,0.4,2.2,0.8,2.2,2.1C-13.7,56-14.5,56.8-16.2,56.8"/>
        <rect x="-5.3" y="49.9" class="st0" width="1" height="6.9"/>
        <polyline class="st0" points="6.9,50.9 6.9,56.7 5.9,56.7 5.9,50.9 3.9,50.9 3.9,49.9 8.9,49.9 8.9,50.9 6.9,50.9 "/>
        <path class="st0" d="M20.1,54.1v2.7h-1v-2.7l-2.5-4.2h1.2l1.1,1.9c0.2,0.4,0.6,1.1,0.7,1.4c0.1-0.3,0.5-0.9,0.7-1.4l1.1-1.9h1.2 L20.1,54.1"/>
        <path class="st0" d="M-92.1,44.9c-0.9,0-1.9,0-3,0.1s-2,0.1-2.7,0.1c-0.2,0-0.4,0-0.7-0.1c-0.3,0-0.4-0.2-0.4-0.5s0.1-0.5,0.4-0.8 s0.9-0.5,1.9-0.6c0.3,0,0.7-0.1,1-0.2s0.6-0.3,0.9-0.6c0.3-0.3,0.5-0.7,0.7-1.2s0.3-1.2,0.3-2.1V9.6c0-0.3-0.1-0.5-0.4-0.7 s-0.7-0.3-1.1-0.3c-0.4-0.1-0.9-0.1-1.4-0.1s-0.9-0.1-1.4-0.1c-0.7-0.1-1.2-0.2-1.5-0.2c-0.3-0.1-0.4-0.3-0.4-0.6 c0-0.3,0.1-0.5,0.3-0.6c0.2-0.1,0.4-0.3,0.7-0.3c0.3-0.1,0.5-0.1,0.8-0.1s0.5,0,0.7,0h5.7c1.6,0,3.1-0.1,4.7-0.2s3.4-0.2,5.4-0.2 c3.3,0,6.4,0.4,9.3,1.3c2.9,0.8,5.4,2.1,7.5,3.9c2.2,1.8,3.9,4,5.2,6.8c1.3,2.8,1.9,6,1.9,9.7c0,2.4-0.5,4.6-1.6,6.7 c-1,2.1-2.4,3.9-4.2,5.5c-1.8,1.6-3.8,2.8-6.2,3.7c-2.4,0.9-4.9,1.4-7.5,1.4L-92.1,44.9 M-88.4,37.1c0,1.1,0.2,2,0.7,2.8 s1.1,1.5,1.8,2c0.8,0.5,1.6,0.9,2.6,1.2c1,0.3,2,0.4,3,0.4c0.8,0,1.8-0.1,3-0.4c1.1-0.3,2.3-0.6,3.5-1.2c1.2-0.5,2.5-1.2,3.7-2.1 s2.3-1.9,3.3-3.2c1-1.2,1.8-2.7,2.3-4.4c0.6-1.7,0.9-3.6,0.9-5.7s-0.3-4.1-0.9-5.9s-1.4-3.3-2.4-4.7c-1-1.4-2.2-2.6-3.5-3.6 s-2.7-1.9-4.2-2.5C-76,9.1-77.5,8.6-79,8.3s-2.9-0.5-4.2-0.5c-1.3,0-2.3,0.1-3,0.2s-1.2,0.3-1.6,0.5c-0.3,0.2-0.5,0.4-0.6,0.7 c-0.1,0.3-0.1,0.5-0.1,0.7L-88.4,37.1L-88.4,37.1z"/>
        <path class="st0" d="M-45.1,46c-1.5,0-2.7-0.2-3.7-0.6c-1-0.4-1.8-1-2.3-1.8c-0.6-0.8-1-1.8-1.2-2.8c-0.2-1.1-0.3-2.3-0.3-3.7 c0-1,0-2,0-3.2s0-2.4,0-3.5c0-1.2,0-2.4,0-3.6s0-2.2,0-3.1c0-0.5-0.2-0.8-0.6-0.9s-0.8-0.2-1.2-0.3c-0.8-0.2-1.3-0.4-1.5-0.5 c-0.3-0.1-0.4-0.3-0.4-0.5c0-0.3,0.1-0.5,0.4-0.5s0.7-0.1,1.1-0.1c0.5,0,0.9,0,1.4,0.1c0.4,0,0.9,0.1,1.4,0.1s0.9,0,1.4-0.1 c0.5,0,0.9-0.1,1.4-0.1c0.4,0,0.7,0.1,0.8,0.3c0.1,0.2,0.2,0.5,0.2,0.9c0,2.8,0,5.6-0.1,8.3c0,2.8-0.1,5.6-0.1,8.3 c0,1.3,0.4,2.3,1.3,3s2.1,1,3.7,1c1.8,0,3.1-0.2,4.1-0.5s1.7-0.8,2.2-1.3s0.8-1.1,1-1.8c0.1-0.7,0.2-1.3,0.2-2c0-2.3,0-4.5,0.1-6.8 c0-2.2,0.1-4.5,0.1-6.8c0-0.2,0-0.3-0.1-0.4s-0.2-0.2-0.4-0.3c-0.2-0.1-0.6-0.2-1-0.3c-0.4-0.1-1-0.3-1.8-0.5 c-0.3-0.1-0.6-0.2-1.1-0.4c-0.5-0.2-0.7-0.4-0.7-0.6s0.1-0.3,0.4-0.4s0.6-0.1,0.9-0.1c0.5,0,1.1,0,1.6,0.1c0.5,0,1.1,0.1,1.6,0.1 c0.6,0,1.3,0,1.9-0.1c0.6,0,1.2-0.1,1.9-0.1c0.2,0,0.5,0.1,0.8,0.2s0.5,0.5,0.5,1.1c0,3.2,0,6.4-0.1,9.5c-0.1,3.2-0.1,6.4-0.1,9.5 c0,0.7,0.2,1.1,0.6,1.3c0.4,0.2,0.7,0.3,1,0.3c1.2,0,2.1,0,2.6,0.1c0.5,0,0.7,0.2,0.7,0.6c0,0.2-0.1,0.4-0.3,0.5 c-0.2,0.1-0.5,0.2-1,0.2c-2.2,0.3-4,0.6-5.3,0.9c-1.3,0.2-2.1,0.4-2.4,0.4c-0.2,0-0.4-0.1-0.4-0.3s-0.1-0.4-0.1-0.7v-1.5 c0-0.5-0.1-0.8-0.4-0.8s-0.6,0.2-1.1,0.6s-1.1,0.8-1.8,1.3c-0.7,0.5-1.6,0.9-2.6,1.3C-42.7,45.8-43.8,46-45.1,46"/>
        <path class="st0" d="M-21.4,9.2c0-0.8-0.2-1.4-0.5-1.8s-0.7-0.6-1.1-0.8c-0.4-0.1-0.8-0.3-1.1-0.3c-0.3-0.1-0.5-0.3-0.5-0.6 c0-0.2,0.1-0.4,0.3-0.5c0.2-0.1,0.5-0.2,1-0.4l4.3-1.6c0.2-0.1,0.3-0.1,0.5-0.1s0.4,0,0.6,0s0.3,0.1,0.5,0.2 c0.1,0.1,0.2,0.5,0.2,0.9V30c0,0.7,0.2,1,0.6,1c0.1,0,0.4-0.1,1-0.4s1.2-0.6,2-1.1c0.8-0.4,1.6-0.9,2.4-1.5 c0.9-0.5,1.6-1.1,2.4-1.6c0.7-0.5,1.3-1,1.8-1.4s0.7-0.7,0.7-0.9c0-0.4-0.1-0.7-0.4-1c-0.3-0.2-0.5-0.4-0.8-0.6 c-0.3-0.1-0.6-0.3-0.8-0.4c-0.3-0.2-0.4-0.4-0.4-0.6s0.1-0.3,0.3-0.4c0.2-0.1,0.4-0.2,0.6-0.2c0.7,0,1.4,0,2.3,0.1 c0.9,0,1.7,0.1,2.6,0.1c0.8,0,1.6,0,2.5-0.1c0.9,0,1.6-0.1,2.2-0.1c0.3,0,0.6,0,0.8,0.1C2.9,21.1,3,21.3,3,21.6 c0,0.2-0.1,0.3-0.3,0.5c-0.2,0.1-0.5,0.3-0.9,0.4c-0.3,0.1-0.7,0.2-1,0.3c-0.4,0.1-0.6,0.2-0.9,0.3c-0.5,0.2-1.4,0.7-2.7,1.4 c-1.3,0.7-2.7,1.5-4.1,2.4c-1.4,0.8-2.7,1.6-3.8,2.4c-1.1,0.7-1.6,1.2-1.6,1.4c0,0.2,0.1,0.4,0.2,0.5s0.2,0.3,0.3,0.3L-1,41.3 c0.6,0.6,1.2,1,1.9,1.3c0.6,0.3,1.1,0.5,1.6,0.7s0.8,0.3,1.1,0.5C3.9,43.9,4,44.1,4,44.3c0,0.4-0.5,0.6-1.6,0.6 c-0.7,0-1.4,0-2.2-0.1c-0.8-0.1-1.7-0.1-2.7-0.1c-0.8,0-1.6,0-2.4,0.1s-1.5,0.1-2.3,0.1c-0.7,0-1.2,0-1.5-0.1s-0.4-0.2-0.4-0.5 s0.2-0.5,0.5-0.6s0.8-0.2,1.3-0.3c0.3,0,0.6-0.1,0.9-0.3c0.2-0.2,0.3-0.4,0.3-0.6s-0.2-0.5-0.7-1l-9.4-8.9 c-0.3-0.3-0.4-0.4-0.6-0.4c-0.3,0-0.4,0.1-0.4,0.3v8.8c0,0.7,0.2,1.2,0.5,1.5s0.6,0.5,0.9,0.5c0.5,0.2,0.9,0.3,1.3,0.4 s0.5,0.2,0.5,0.5s-0.2,0.4-0.5,0.5s-0.6,0.1-1,0.1c-0.8,0-1.5,0-2.2-0.1s-1.4-0.1-2.1-0.1c-0.8,0-1.6,0-2.4,0.1 c-0.9,0.1-1.6,0.1-2.1,0.1c-0.2,0-0.5,0-0.9-0.1s-0.6-0.2-0.6-0.5s0.1-0.5,0.3-0.6c0.2-0.1,0.5-0.2,0.8-0.3 c0.4-0.1,0.8-0.2,1.2-0.3c0.4-0.1,0.7-0.2,1-0.4c0.3-0.2,0.5-0.4,0.7-0.8c0.1-0.3,0.2-0.8,0.2-1.5V9.2"/>
        <path class="st0" d="M8.2,30.3c-0.1,0.2-0.1,0.5-0.1,0.9s0,0.8,0,1.3c0,1.4,0.1,2.7,0.3,3.9c0.2,1.3,0.7,2.4,1.3,3.4 c0.7,1,1.6,1.8,2.8,2.4c1.2,0.6,2.8,0.9,4.7,0.9c1.2,0,2.2-0.1,2.8-0.4c0.7-0.3,1.2-0.5,1.6-0.9c0.4-0.3,0.7-0.6,0.9-0.9 c0.2-0.3,0.4-0.4,0.7-0.4c0.4,0,0.6,0.2,0.6,0.5c0,0.1-0.2,0.5-0.5,1s-0.9,1.1-1.6,1.7c-0.8,0.6-1.7,1.2-2.9,1.7 c-1.2,0.5-2.6,0.7-4.2,0.7c-3.5,0-6.2-1.1-8-3.4c-1.9-2.3-2.9-5.4-2.9-9.3c0-1.5,0.2-3,0.7-4.6s1.2-3,2.1-4.3s2.1-2.3,3.6-3.2 c1.4-0.8,3.1-1.3,5.1-1.3c1.8,0,3.3,0.3,4.6,1c1.2,0.7,2.2,1.5,3,2.4s1.3,1.9,1.6,2.9s0.5,1.9,0.5,2.5s-0.1,1-0.2,1.2 s-0.5,0.3-1,0.3L8.2,30.3 M14.3,28.4c1.4,0,2.5-0.1,3.3-0.2s1.5-0.3,2-0.5c0.5-0.3,0.8-0.6,0.9-0.9c0.1-0.4,0.2-0.9,0.2-1.5 c0-1.1-0.4-2-1.3-2.7s-2-1.1-3.3-1.1c-1.1,0-2.2,0.2-3.1,0.7s-1.7,1.1-2.3,1.7c-0.6,0.7-1.1,1.4-1.4,2.1s-0.5,1.3-0.5,1.8 c0,0.1,0,0.2,0.1,0.3c0.1,0.1,0.3,0.1,0.6,0.2c0.4,0,0.9,0.1,1.6,0.1C11.9,28.4,12.9,28.4,14.3,28.4z"/>
      </g>
    </svg>
    <h1>Duke Eats</h1>`;
  root.appendChild(headerDiv);

  const pageContentDiv = document.createElement('div');
  pageContentDiv.className = 'page-content';
  root.appendChild(pageContentDiv);


  if (isLoading) {
    pageContentDiv.innerHTML = `<div class="loading" role="status" aria-live="polite">
                                <p>Generating your meal plan...</p>
                                <svg width="50" height="50" viewBox="0 0 50 50" style="margin:auto;display:block;">
                                  <circle cx="25" cy="25" r="20" fill="none" stroke="#012169" stroke-width="4" stroke-dasharray="31.415, 31.415" transform="rotate(90 25 25)">
                                    <animateTransform attributeName="transform" type="rotate" repeatCount="indefinite" dur="1s" values="0 25 25;360 25 25" keyTimes="0;1"></animateTransform>
                                  </circle>
                                </svg>
                              </div>`;
    return;
  }

  if (errorMessage) {
    pageContentDiv.innerHTML = `<div class="error-message" role="alert">${escapeHtml(errorMessage)}</div>`;
     const backButton = createButton('Try Again', () => {
      errorMessage = ''; 
      currentPage = 'goalInput'; 
      renderApp();
    }, ['button-secondary']);
    pageContentDiv.appendChild(backButton);
    return;
  }

  switch (currentPage) {
    case 'home':
      renderHomePage(pageContentDiv);
      break;
    case 'goalInput':
      renderGoalInputPage(pageContentDiv);
      break;
    case 'mealPlan':
      renderMealPlanPage(pageContentDiv);
      break;
  }
}

function renderHomePage(container: HTMLElement) {
  const pageDiv = document.createElement('div');
  pageDiv.className = 'page text-center';
  pageDiv.innerHTML = `
    <h2>Welcome to Duke Eats!</h2>
    <p>Your personalized meal planner for dining on campus.</p>
    <p>Tell us your goals, and we'll help you find the best meals at Duke's dining locations using your local dining database.</p>
  `;
  const startButton = createButton('Get Started', () => {
    currentPage = 'goalInput';
    renderApp();
  });
  pageDiv.appendChild(startButton);
  container.appendChild(pageDiv);
}

function renderGoalInputPage(container: HTMLElement) {
  const pageDiv = document.createElement('div');
  pageDiv.className = 'page';
  pageDiv.innerHTML = `<h2>Tell Us About Yourself</h2>`;

  const form = document.createElement('form');
  form.id = 'goalForm';
  form.setAttribute('aria-labelledby', 'formTitle');
  pageDiv.querySelector('h2')!.id = 'formTitle';

  const restrictionsGroup = createFormGroup('Dietary Restrictions (select all that apply)', 'dietaryRestrictionsSection');
  const restrictions = ['Vegetarian', 'Vegan', 'Gluten-Free', 'Dairy-Free', 'Nut-Free', 'Halal', 'Kosher', 'No Red Meat', 'No Pork', 'No Poultry', 'No Fish/Shellfish'];
  restrictions.forEach(r => {
    restrictionsGroup.appendChild(createCheckbox(r, 'dietaryRestrictions', userGoals.dietaryRestrictions.includes(r), (checked) => {
      if (checked) userGoals.dietaryRestrictions.push(r);
      else userGoals.dietaryRestrictions = userGoals.dietaryRestrictions.filter(item => item !== r);
    }));
  });
  form.appendChild(restrictionsGroup);

  const otherNotesGroup = createFormGroup('Other dietary notes or specific allergies (e.g., allergic to strawberries, avoid spicy food)', 'otherDietaryNotesLabel');
  const otherNotesInput = createTextArea('otherDietaryNotes', userGoals.otherDietaryNotes, (value) => userGoals.otherDietaryNotes = value, 'otherDietaryNotesLabel');
  otherNotesGroup.appendChild(otherNotesInput);
  form.appendChild(otherNotesGroup);

  const primaryGoalGroup = createFormGroup('Primary Health/Body Goal', 'primaryGoalSection');
  const goals = [
    { label: 'Weight Loss', value: 'weightLoss' },
    { label: 'Weight Gain', value: 'weightGain' },
    { label: 'Muscle Gain', value: 'muscleGain' },
    { label: 'Maintain Weight', value: 'maintainWeight' },
    { label: 'General Healthy Eating', value: 'healthyEating' }
  ];
  goals.forEach(g => {
    primaryGoalGroup.appendChild(createRadio('primaryGoal', g.label, g.value as UserGoals['primaryGoal'], userGoals.primaryGoal === g.value, (value) => userGoals.primaryGoal = value as UserGoals['primaryGoal']));
  });
  form.appendChild(primaryGoalGroup);

  const specificGoalsGroup = createFormGroup('Any specific nutritional targets or goals? (e.g., high protein, low carb, >2000 calories, less than 50g sugar)', 'specificGoalsLabel');
  const specificGoalsInput = createTextArea('specificGoals', userGoals.specificGoals, (value) => userGoals.specificGoals = value, 'specificGoalsLabel');
  specificGoalsGroup.appendChild(specificGoalsInput);
  form.appendChild(specificGoalsGroup);

  const mealsConsumedGroup = createFormGroup('Which meals do you typically eat?', 'mealsConsumedSection');
  mealsConsumedGroup.appendChild(createCheckbox('Breakfast', 'mealsConsumed.breakfast', userGoals.mealsConsumed.breakfast, (checked) => userGoals.mealsConsumed.breakfast = checked));
  mealsConsumedGroup.appendChild(createCheckbox('Lunch', 'mealsConsumed.lunch', userGoals.mealsConsumed.lunch, (checked) => userGoals.mealsConsumed.lunch = checked));
  mealsConsumedGroup.appendChild(createCheckbox('Dinner', 'mealsConsumed.dinner', userGoals.mealsConsumed.dinner, (checked) => userGoals.mealsConsumed.dinner = checked));
  mealsConsumedGroup.appendChild(createCheckbox('Snacks', 'mealsConsumed.snacks', userGoals.mealsConsumed.snacks, (checked) => userGoals.mealsConsumed.snacks = checked));
  form.appendChild(mealsConsumedGroup);

  const submitButton = createButton('Generate My Plan', handleSubmitGoals);
  submitButton.type = 'submit';
  form.appendChild(submitButton);

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    handleSubmitGoals();
  });

  pageDiv.appendChild(form);
  container.appendChild(pageDiv);
}

async function handleSubmitGoals() {
  isLoading = true;
  errorMessage = '';
  mealPlan = null;
  renderApp(); // Show loading state

  try {
    // This is where you'll call your Python backend.
    // The URL '/api/get_meal_plan' is a placeholder.
    // You'll need to set up a Python server (e.g., Flask, FastAPI)
    // to handle this request and call your agent.py.
    const response = await fetch('/api/get_meal_plan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(userGoals),
    });

    if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`Backend server error: ${response.status} ${errorData}`);
    }

    const parsedPlan = await response.json() as DailyMealPlan;

    // Ensure meals not consumed by user are set to null in the plan
    if (!userGoals.mealsConsumed.breakfast) parsedPlan.breakfast = null;
    if (!userGoals.mealsConsumed.lunch) parsedPlan.lunch = null;
    if (!userGoals.mealsConsumed.dinner) parsedPlan.dinner = null;
    if (!userGoals.mealsConsumed.snacks) parsedPlan.snacks = null;
    
    mealPlan = parsedPlan;
    currentPage = 'mealPlan';
  } catch (error) {
    console.error("Error fetching meal plan from backend:", error);
    errorMessage = "Sorry, we couldn't generate a meal plan from the backend at this time.";
    if (error instanceof Error) {
        errorMessage += ` Details: ${error.message}`;
    }
  } finally {
    isLoading = false;
    renderApp();
  }
}

function renderMealPlanPage(container: HTMLElement) {
  const pageDiv = document.createElement('div');
  pageDiv.className = 'page';
  pageDiv.innerHTML = `<h2>${mealPlan?.dayName || "Your Meal Plan"}</h2>`;

  if (!mealPlan) {
    pageDiv.innerHTML += `<p>No meal plan available.</p>`;
    container.appendChild(pageDiv);
    return;
  }

  const mealsToShow: (keyof DailyMealPlan)[] = ['breakfast', 'lunch', 'dinner', 'snacks'];
  let planIsEmpty = true;

  mealsToShow.forEach(mealKey => {
    if (userGoals.mealsConsumed[mealKey as keyof UserGoals['mealsConsumed']]) {
      const mealData = mealPlan[mealKey] as Meal | null;
      const mealName = mealKey.charAt(0).toUpperCase() + mealKey.slice(1);
      
      const mealDayDiv = document.createElement('div');
      mealDayDiv.className = 'meal-plan-day';
      mealDayDiv.innerHTML = `<h3 id="${mealKey}Title">${escapeHtml(mealName)}</h3>`;

      if (mealData && mealData.items && mealData.items.length > 0) {
        planIsEmpty = false;
        const mealCard = document.createElement('div');
        mealCard.className = 'meal-card';
        mealCard.setAttribute('aria-labelledby', `${mealKey}Title`);
        mealCard.innerHTML = `<h4>At: ${escapeHtml(mealData.restaurant)}</h4>`;
        
        const itemList = document.createElement('ul');
        itemList.setAttribute('aria-label', `${escapeHtml(mealName)} items at ${escapeHtml(mealData.restaurant)}`);
        mealData.items.forEach(item => {
          const listItem = document.createElement('li');
          let itemText = `<strong>${escapeHtml(item.name)}</strong>`;
          if (item.calories) itemText += ` (~${item.calories} cal`;
          if (item.protein) itemText += `, ${item.protein}g protein`;
          if (item.calories) itemText += `)`;
          if (item.description) itemText += ` - <small>${escapeHtml(item.description)}</small>`;
          listItem.innerHTML = itemText;
          itemList.appendChild(listItem);
        });
        mealCard.appendChild(itemList);
        mealDayDiv.appendChild(mealCard);
      } else {
        mealDayDiv.innerHTML += `<p>No specific recommendation for ${escapeHtml(mealName.toLowerCase())} based on your goals, or you've opted out of this meal.</p>`;
      }
      pageDiv.appendChild(mealDayDiv);
    }
  });

  if (planIsEmpty && !isLoading && !errorMessage) {
     pageDiv.innerHTML += `<p>We couldn't find any specific recommendations matching all your criteria for the selected meals. You might want to broaden your preferences or try again.</p>`;
  }

  const adjustButton = createButton('Adjust Goals', () => {
    currentPage = 'goalInput';
    renderApp();
  }, ['button-secondary']);
  pageDiv.appendChild(adjustButton);
  
  const newPlanButton = createButton('Get Another Plan', () => {
    handleSubmitGoals(); 
  });
  newPlanButton.style.marginLeft = '10px';
  pageDiv.appendChild(newPlanButton);

  container.appendChild(pageDiv);
}

// --- Helper Functions ---
function createFormGroup(labelText: string, sectionIdSuffix: string): HTMLElement {
  const div = document.createElement('div');
  div.className = 'form-group';
  div.setAttribute('role', 'group');
  div.setAttribute('aria-labelledby', `label_${sectionIdSuffix}`);

  const label = document.createElement('label');
  label.textContent = labelText;
  label.id = `label_${sectionIdSuffix}`;
  div.appendChild(label);
  return div;
}

function createCheckbox(labelText: string, name: string, checked: boolean, onChange: (isChecked: boolean) => void): HTMLElement {
  const uniqueId = name.replace(/\./g, '_') + '_' + labelText.replace(/\W/g, '');
  const label = document.createElement('label');
  label.className = 'checkbox-label';
  label.htmlFor = uniqueId;

  const input = document.createElement('input');
  input.type = 'checkbox';
  input.name = name;
  input.checked = checked;
  input.id = uniqueId;
  input.onchange = () => onChange(input.checked);
  
  const textNode = document.createTextNode(' ' + labelText);
  label.appendChild(input);
  label.appendChild(textNode);
  
  const container = document.createElement('div');
  container.className = 'checkbox-group-item';
  container.appendChild(label);
  return container;
}

function createRadio(name: string, labelText: string, value: string, checked: boolean, onChange: (value: string) => void): HTMLElement {
  const uniqueId = name + '_' + value.replace(/\W/g, '');
  const label = document.createElement('label');
  label.className = 'radio-label';
  label.htmlFor = uniqueId;

  const input = document.createElement('input');
  input.type = 'radio';
  input.name = name;
  input.value = value;
  input.checked = checked;
  input.id = uniqueId;
  input.onchange = () => onChange(value);
  
  const textNode = document.createTextNode(' ' + labelText);
  label.appendChild(input);
  label.appendChild(textNode);

  const container = document.createElement('div');
  container.className = 'radio-group-item';
  container.appendChild(label);
  return container;
}

function createTextArea(name: string, value: string, onInput: (value: string) => void, labelIdToAssociate: string): HTMLTextAreaElement {
  const textarea = document.createElement('textarea');
  textarea.name = name;
  textarea.value = value;
  textarea.id = name + '_input';
  textarea.oninput = () => onInput(textarea.value);
  textarea.setAttribute('aria-labelledby', labelIdToAssociate);
  textarea.rows = 3;
  return textarea;
}

function createButton(text: string, onClick: () => void, classes: string[] = []): HTMLButtonElement {
  const button = document.createElement('button');
  button.textContent = text;
  button.className = 'button ' + classes.join(' ');
  button.type = 'button';
  button.onclick = onClick;
  return button;
}

function escapeHtml(unsafe: string): string {
    if (unsafe === null || typeof unsafe === 'undefined') return '';
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// --- Initial Render ---
renderApp();
