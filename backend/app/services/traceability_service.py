class TraceabilityService:
    def summarize(self,context,scenarios,test_cases):
        req_to_scenarios={};story_to_scenarios={};ac_to_scenarios={};scenario_to_cases={};case_to_requirements={}
        for s in scenarios:
            for x in s.requirement_ids:req_to_scenarios.setdefault(x,[]).append(s.scenario_id)
            for x in s.user_story_ids:story_to_scenarios.setdefault(x,[]).append(s.scenario_id)
            for x in s.acceptance_criteria_ids:ac_to_scenarios.setdefault(x,[]).append(s.scenario_id)
        for c in test_cases: scenario_to_cases.setdefault(c.scenario_id,[]).append(c.test_case_id);case_to_requirements[c.test_case_id]=c.requirement_ids
        return {"requirement_to_scenarios":req_to_scenarios,"user_story_to_scenarios":story_to_scenarios,"acceptance_criterion_to_scenarios":ac_to_scenarios,"scenario_to_test_cases":scenario_to_cases,"test_case_to_requirements":case_to_requirements}
