/**
 * process-feedback Edge Function
 * 
 * Called when a new feedback_response row is inserted.
 * Performs NLP analysis + embedding generation via OpenRouter
 * and stores results in feedback_analysis table.
 * 
 * Deployment: InsForge Dashboard → Edge Functions → New Function → slug: process-feedback
 */

import { createClient } from 'npm:@insforge/sdk';

const OPENROUTER_URL = 'https://openrouter.ai/api/v1';
const NLP_MODEL = 'google/gemini-2.5-flash:free';
const EMBED_MODEL = 'openai/text-embedding-3-small';

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

  const openrouterKey = Deno.env.get('OPENROUTER_API_KEY');
  const insforgeUrl = Deno.env.get('INSFORGE_BASE_URL');
  const anonKey = Deno.env.get('ANON_KEY');

  if (!openrouterKey || !insforgeUrl || !anonKey) {
    return new Response(JSON.stringify({ error: 'Missing environment variables' }), {
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

  const record = payload.record || payload;
  const response_id = payload.response_id || record.id;
  const aspect_most_valuable = record.aspect_most_valuable || '';
  const improvements_suggestions = record.improvements_suggestions || '';
  const future_topics = record.future_topics || '';
  const session_rating = record.session_rating;

  if (!response_id) {
    return new Response(JSON.stringify({ error: 'response_id required' }), {
      status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Combine all text fields
  const combinedText = [
    aspect_most_valuable,
    improvements_suggestions,
    future_topics,
  ].filter(Boolean).join(' | ');

  if (!combinedText.trim()) {
    return new Response(JSON.stringify({ skipped: true, reason: 'empty text' }), {
      status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const client = createClient({ baseUrl: insforgeUrl, anonKey });

  try {
    // ── Step 1: NLP Analysis via OpenRouter ──────────────────────────
    const nlpPrompt = `Analyze this student feedback about an alumni speaker session. Return ONLY valid JSON.

Feedback:
Most valuable aspect: "${aspect_most_valuable}"
Suggestions for improvement: "${improvements_suggestions}"
Future topics requested: "${future_topics}"
Session rating: ${session_rating}/5

Return JSON:
{
  "sentiment_label": "POSITIVE" or "NEUTRAL" or "NEGATIVE",
  "sentiment_score": <float -1.0 to 1.0>,
  "keywords": ["word1", "word2", "word3"],
  "keyphrases": ["phrase 1", "phrase 2"],
  "is_actionable": true or false,
  "category": "infrastructure" or "content" or "speaker" or "general",
  "actionable_items": ["item1", "item2"]
}`;

    const nlpResp = await fetch(`${OPENROUTER_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${openrouterKey}`,
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://mamta-feedback.hf.space',
        'X-Title': 'Alumni Feedback System',
      },
      body: JSON.stringify({
        model: NLP_MODEL,
        messages: [{ role: 'user', content: nlpPrompt }],
        response_format: { type: 'json_object' },
        temperature: 0.1,
      }),
    });

    if (!nlpResp.ok) {
      throw new Error(`OpenRouter NLP failed: ${nlpResp.status} ${await nlpResp.text()}`);
    }

    const nlpData = await nlpResp.json();
    const nlpResult = JSON.parse(nlpData.choices[0].message.content);

    // ── Step 2: Generate Embedding ──────────────────────────────────
    const embedResp = await fetch(`${OPENROUTER_URL}/embeddings`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${openrouterKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: EMBED_MODEL,
        input: combinedText.slice(0, 8000),
        dimensions: 768,  // Match existing vector(768) schema
      }),
    });

    let embedding: number[] | null = null;
    if (embedResp.ok) {
      const embedData = await embedResp.json();
      embedding = embedData.data[0].embedding;
    } else {
      console.error('Embedding generation failed:', await embedResp.text());
    }

    // ── Step 3: Save NLP results to feedback_analysis ───────────────
    const analysisPayload = {
      response_id,
      sentiment_label: nlpResult.sentiment_label ?? 'NEUTRAL',
      sentiment_score: nlpResult.sentiment_score ?? 0.0,
      keywords_json: JSON.stringify(nlpResult.keywords ?? []),
      keyphrases_json: JSON.stringify(nlpResult.keyphrases ?? []),
      is_actionable: nlpResult.is_actionable ?? false,
      category: nlpResult.category ?? 'general',
      actionable_items_json: JSON.stringify(nlpResult.actionable_items ?? []),
      processed_at: new Date().toISOString(),
      model_used: NLP_MODEL,
    };

    const { error: insertError } = await client.database
      .from('feedback_analysis')
      .upsert([analysisPayload], { onConflict: 'response_id' });

    if (insertError) {
      console.error('Failed to save feedback_analysis:', insertError);
    }

    // ── Step 4: Update embedding in feedback_responses ──────────────
    if (embedding) {
      const { error: embedUpdateError } = await client.database
        .from('feedback_responses')
        .update({ embedding: JSON.stringify(embedding) })
        .eq('id', response_id);

      if (embedUpdateError) {
        console.error('Failed to update embedding:', embedUpdateError);
      }
    }

    return new Response(JSON.stringify({
      success: true,
      response_id,
      sentiment: nlpResult.sentiment_label,
      keywords: nlpResult.keywords,
      embedding_generated: !!embedding,
    }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (err) {
    console.error('process-feedback error:', err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
}
