# Salesforce-Native Deployment Path (illustrative, not executed)

These files are NOT run by the Streamlit demo. They document how this workflow would
actually ship inside a real Salesforce org, for interview credibility on Apex/Flow/Einstein.

TODO(weaponx): write the explanation of the production path — Record-Triggered Flow ->
Invocable Apex -> outbound callout to this service -> response written back to the Lead
record via AI_Score__c / AI_Routing__c / AI_Rep_Brief__c -> optional Platform Event for
async UI refresh — plus a note on where Einstein Lead Scoring would sit in a real deployment.
See plan section "Salesforce-Native Deployment Path".
