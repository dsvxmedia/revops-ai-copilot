/**
 * RevOpsCopilotInvocable
 * -----------------------------------------------------------------------------
 * ILLUSTRATIVE APEX ONLY. Not deployed to any org and not executed by the demo.
 * It shows how a Record-Triggered Flow would call an Invocable Apex action that
 * makes an outbound HTTP callout to the RevOps Copilot service and writes the
 * score / routing / rep-brief back onto the Lead via custom fields.
 *
 * Production wiring: Named Credential "RevOps_Copilot_API" points at the
 * containerized Python service; the callout is bulk-safe (one request per
 * invocation batch) and runs @future/Queueable from the Flow to respect the
 * "no callouts before DML" governor rules in a trigger context.
 *
 * See plan section "Salesforce-Native Deployment Path".
 */
public with sharing class RevOpsCopilotInvocable {

    // ---- Flow <-> Apex data contract ---------------------------------------
    public class ScoreRequest {
        @InvocableVariable(required=true label='Lead Id')
        public Id leadId;

        @InvocableVariable(label='Company')
        public String company;

        @InvocableVariable(label='Industry')
        public String industry;

        @InvocableVariable(label='Annual Revenue')
        public Decimal annualRevenue;

        @InvocableVariable(label='Number Of Employees')
        public Integer numberOfEmployees;

        @InvocableVariable(label='Lead Source')
        public String leadSource;

        @InvocableVariable(label='Request Type')
        public String requestType;

        @InvocableVariable(label='Description')
        public String description;
    }

    public class ScoreResponse {
        @InvocableVariable(label='Combined Score')
        public Decimal combinedScore;

        @InvocableVariable(label='Routing Outcome')
        public String routingOutcome;

        @InvocableVariable(label='Needs Human Review')
        public Boolean needsHumanReview;

        @InvocableVariable(label='Rep Brief Summary')
        public String repBriefSummary;
    }

    /**
     * Invocable entry point. Flow passes a list of ScoreRequest; we return a
     * parallel list of ScoreResponse. The callout itself is dispatched async so
     * it is safe from a record-triggered context.
     */
    @InvocableMethod(label='Score and Route Lead' description='Calls the RevOps Copilot service to score, route, and brief a Lead.')
    public static List<ScoreResponse> scoreAndRoute(List<ScoreRequest> requests) {
        List<ScoreResponse> responses = new List<ScoreResponse>();
        Set<Id> leadIds = new Set<Id>();
        for (ScoreRequest req : requests) {
            leadIds.add(req.leadId);
            // Synchronous placeholder response so the Flow can continue; the
            // authoritative write-back happens in the async callout below.
            ScoreResponse placeholder = new ScoreResponse();
            placeholder.routingOutcome = 'Pending';
            placeholder.needsHumanReview = false;
            responses.add(placeholder);
        }
        // Dispatch the real callout + write-back asynchronously.
        if (!leadIds.isEmpty()) {
            scoreCalloutAsync(new List<Id>(leadIds));
        }
        return responses;
    }

    @future(callout=true)
    private static void scoreCalloutAsync(List<Id> leadIds) {
        List<Lead> toUpdate = new List<Lead>();
        for (Lead ld : [
            SELECT Id, Company, Industry, AnnualRevenue, NumberOfEmployees,
                   LeadSource, RequestType__c, Description
            FROM Lead
            WHERE Id IN :leadIds
        ]) {
            try {
                HttpRequest httpReq = new HttpRequest();
                httpReq.setEndpoint('callout:RevOps_Copilot_API/v1/score');
                httpReq.setMethod('POST');
                httpReq.setHeader('Content-Type', 'application/json');
                httpReq.setTimeout(30000);

                Map<String, Object> payload = new Map<String, Object>{
                    'lead_id'            => ld.Id,
                    'Company'            => ld.Company,
                    'Industry'           => ld.Industry,
                    'AnnualRevenue'      => ld.AnnualRevenue,
                    'NumberOfEmployees'  => ld.NumberOfEmployees,
                    'LeadSource'         => ld.LeadSource,
                    'RequestType'        => ld.RequestType__c,
                    'Description'        => ld.Description
                };
                httpReq.setBody(JSON.serialize(payload));

                HttpResponse res = new Http().send(httpReq);
                if (res.getStatusCode() == 200) {
                    Map<String, Object> body =
                        (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
                    Lead upd = new Lead(Id = ld.Id);
                    upd.AI_Score__c = (Decimal) body.get('combined_score');
                    upd.AI_Routing__c = (String) body.get('routing_outcome');
                    upd.AI_Needs_Human_Review__c = (Boolean) body.get('needs_human_review');
                    upd.AI_Rep_Brief__c = (String) body.get('rep_brief_summary');
                    toUpdate.add(upd);
                } else {
                    System.debug(LoggingLevel.WARN,
                        'RevOps Copilot callout failed: ' + res.getStatusCode());
                }
            } catch (Exception ex) {
                // Graceful degrade: log and leave the Lead for manual handling.
                System.debug(LoggingLevel.ERROR, 'RevOps Copilot error: ' + ex.getMessage());
            }
        }
        if (!toUpdate.isEmpty()) {
            update toUpdate;
            // Optional: publish a Platform Event so LWCs can refresh the UI async.
            // EventBus.publish(new Lead_Scored__e(LeadId__c = ...));
        }
    }
}
