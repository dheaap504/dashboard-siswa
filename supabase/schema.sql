-- Jalankan di Supabase > SQL Editor
create table if not exists public.student_performance (
  id                          bigint generated always as identity primary key,
  created_at                  timestamptz not null default now(),
  hours_studied               int  not null check (hours_studied between 0 and 80),
  attendance                  int  not null check (attendance between 0 and 100),
  parental_involvement        text check (parental_involvement in ('Low','Medium','High')),
  access_to_resources         text check (access_to_resources in ('Low','Medium','High')),
  extracurricular_activities  text check (extracurricular_activities in ('Yes','No')),
  sleep_hours                 int  check (sleep_hours between 0 and 24),
  previous_scores             int  check (previous_scores between 0 and 100),
  motivation_level            text check (motivation_level in ('Low','Medium','High')),
  internet_access             text check (internet_access in ('Yes','No')),
  tutoring_sessions           int  check (tutoring_sessions >= 0),
  family_income               text check (family_income in ('Low','Medium','High')),
  teacher_quality             text check (teacher_quality in ('Low','Medium','High')),
  school_type                 text check (school_type in ('Public','Private')),
  peer_influence              text check (peer_influence in ('Negative','Neutral','Positive')),
  physical_activity           int  check (physical_activity >= 0),
  learning_disabilities       text check (learning_disabilities in ('Yes','No')),
  parental_education_level    text check (parental_education_level in ('High School','College','Postgraduate')),
  distance_from_home          text check (distance_from_home in ('Near','Moderate','Far')),
  gender                      text check (gender in ('Male','Female')),
  exam_score                  int  not null check (exam_score between 0 and 100)
);

-- Dashboard hanya BACA dengan anon key; tulis hanya lewat service_role key (aman).
alter table public.student_performance enable row level security;
create policy "public read" on public.student_performance for select using (true);
