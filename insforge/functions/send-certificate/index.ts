/**
 * send-certificate Edge Function
 *
 * Called when a new certificate_job row is inserted with status='pending'.
 * Fetches job details from DB, calls Google Apps Script to generate
 * and email the certificate, then updates job status.
 *
 * Deployment: InsForge Dashboard → Edge Functions → New Function → slug: send-certificate
 */

import { createClient } from 'npm:@insforge/sdk';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export default async function handler(req: Request): Promise<Response> {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const insforgeUrl = Deno.env.get('INSFORGE_BASE_URL') || 'https://ajas4w5j.us-east.insforge.app';
  const anonKey = Deno.env.get('ANON_KEY') || 'anon_31d0b6c930373a82bbb50878968050a302c65093eff7b272135f271d205e3c52';

  const client = createClient({ baseUrl: insforgeUrl, anonKey });

  let appsScriptUrl = Deno.env.get('APPS_SCRIPT_URL');
  let appsScriptSecret = Deno.env.get('APPS_SCRIPT_SECRET');

  if (!appsScriptUrl) {
    try {
      const { data: configRows } = await client.database
        .from('system_config')
        .select('*');
      if (configRows) {
        const config = Object.fromEntries(configRows.map(r => [r.key, r.value]));
        appsScriptUrl = config['APPS_SCRIPT_URL'];
        appsScriptSecret = config['APPS_SCRIPT_SECRET'];
      }
    } catch (e) {
      console.error('Failed to load config from DB:', e);
    }
  }

  if (!insforgeUrl || !anonKey || !appsScriptUrl) {
    return new Response(JSON.stringify({ error: 'Missing environment variables or DB configuration' }), {
      status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const job_id = payload.job_id || payload.record?.id;
  if (!job_id) {
    return new Response(JSON.stringify({ error: 'job_id required' }), {
      status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    // ── Step 1: Fetch job with student + event details ───────────────
    const { data: jobs, error: fetchError } = await client.database
      .from('certificate_jobs')
      .select('*, students(*), events(*)')
      .eq('id', job_id)
      .limit(1);

    if (fetchError || !jobs?.length) {
      throw new Error(`Job not found: ${job_id}`);
    }

    const job = jobs[0];

    // Skip if already processed
    if (job.status !== 'pending') {
      return new Response(JSON.stringify({ skipped: true, status: job.status }), {
        status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    // ── Step 2: Mark job as processing ──────────────────────────────
    await client.database
      .from('certificate_jobs')
      .update({ status: 'processing', attempts: (job.attempts || 0) + 1 })
      .eq('id', job_id);

    // ── Step 3: Call Google Apps Script ─────────────────────────────
    let templateId = job.events?.template_id ?? '';
    if (templateId) {
      const match = templateId.match(/\/d\/([a-zA-Z0-9-_]+)/);
      if (match) {
        templateId = match[1];
      }
    }

    const gasPayload: Record<string, any> = {
      action: 'generate_certificate',
      template_id: templateId,
      student_name: job.students?.name ?? '',
      student_email: job.students?.email ?? '',
      roll_no: job.students?.roll_no ?? '',
      speaker_name: job.events?.speaker_name ?? '',
      venue_date: job.events?.venue_date ?? '',
      lecture_title: job.events?.lecture_title ?? '',
      department: job.students?.department ?? '',
    };

    if (appsScriptSecret) {
      gasPayload['secret'] = appsScriptSecret;
    }

    const gasResp = await fetch(appsScriptUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(gasPayload),
    });

    const gasOk = gasResp.ok;
    let gasBodyText = '';
    let gasData: any = {};
    try {
      gasBodyText = await gasResp.text();
      gasData = JSON.parse(gasBodyText);
    } catch (_) {
      // not JSON or empty
    }

    const isSuccess = gasOk && (gasData.success === true);

    // Extract overflow warnings
    let warningLog: string | null = null;
    if (isSuccess && gasData.data && Array.isArray(gasData.data.overflow_warnings) && gasData.data.overflow_warnings.length > 0) {
      warningLog = JSON.stringify({
        type: 'layout_warning',
        message: `${gasData.data.overflow_warnings.length} shape(s) may have text overflow`,
        details: gasData.data.overflow_warnings
      });
    }

    const finalStatus = isSuccess ? 'completed' : 'failed';
    const errorLog = isSuccess 
      ? warningLog 
      : (gasData.message ? `${gasData.message}${gasData.data ? ': ' + JSON.stringify(gasData.data) : ''}` : gasBodyText || 'Unknown error');

    // ── Step 4: Update job status ────────────────────────────────────
    await client.database
      .from('certificate_jobs')
      .update({
        status: finalStatus,
        generated_at: new Date().toISOString(),
        error_log: errorLog ? errorLog.slice(0, 1000) : null,
      })
      .eq('id', job_id);

    return new Response(JSON.stringify({
      success: isSuccess,
      job_id,
      student: job.students?.name,
      status: finalStatus,
    }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (err) {
    console.error('send-certificate error:', err);

    // Mark job as failed
    try {
      await client.database
        .from('certificate_jobs')
        .update({ status: 'failed', error_log: String(err).slice(0, 1000) })
        .eq('id', job_id);
    } catch (_) {
      // ignore secondary error
    }

    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
}
