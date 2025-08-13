import json
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib import utils
from resources.lib.singleton_base import Singleton

class ResultsManager(Singleton):
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.jsonrpc = JSONRPC()
            from resources.lib.query_manager import QueryManager
            from resources.lib.config_manager import Config
            self.query_manager = QueryManager(Config().db_path)
            self._initialized = True

    def search_movie_by_criteria(self, title, year=None, director=None):
        try:
            return self.query_manager.get_matched_movies(title, year, director)
        except Exception as e:
            utils.log(f"Error searching movies: {e}", "ERROR")
            return []

    def build_display_items_for_list(self, list_id: int):
        """Resolve list items for display.
        Reference/provider/search_history items are resolved via Title+Year
        derived from imdb_exports; external items use stored metadata.
        """
        import json
        rows = self.query_manager.fetch_list_items_with_details(list_id)
        external, refs = [], []
        for r in rows:
            src = (r.get('source') or '').lower()
            if src == 'external':
                external.append(r)
                continue
            imdb = r.get('imdbnumber')
            title, year = '', 0

            # Try to get title/year from imdb_exports first
            if imdb:
                try:
                    q = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                    hit = self.query_manager.execute_query(q, (imdb,)) or []
                    if hit:
                        rec = hit[0]
                        title = (rec.get('title') if isinstance(rec, dict) else rec[0]) or ''
                        year = int((rec.get('year') if isinstance(rec, dict) else rec[1]) or 0)
                        # utils.log(f"Found in imdb_exports: {title} ({year}) for IMDB {imdb}", "DEBUG")
                    else:
                        utils.log(f"No imdb_exports entry found for IMDB {imdb}", "DEBUG")
                except Exception as e:
                    utils.log(f"Error querying imdb_exports for {imdb}: {str(e)}", "ERROR")

            # Fallback to stored data if imdb lookup failed
            if not title:
                title = r.get('title') or ''
                utils.log(f"Using fallback title: {title}", "DEBUG")

            if not year:
                try:
                    year = int(r.get('year') or 0)
                    utils.log(f"Using fallback year: {year}", "DEBUG")
                except Exception:
                    year = 0

            # If we still have no title, try to extract from the original stored data
            if not title or title == '':
                # Check if there's any identifying information we can use
                stored_title = r.get('title', '')
                if stored_title and stored_title.strip():
                    title = stored_title.strip()
                    utils.log(f"Using stored title as final fallback: {title}", "DEBUG")
                else:
                    title = f"IMDB: {imdb}" if imdb else "Unknown Movie"
                    utils.log(f"Using IMDB ID as title fallback: {title}", "WARNING")

            refs.append({'imdb': imdb, 'title': title, 'year': year})

        resolved = []
        # ---- Batch resolve via one JSON-RPC call using OR of (title AND year) ----
        batch_pairs = [{"title": r.get("title"), "year": r.get("year")} for r in refs]
        utils.log(f"Batch lookup pairs: {batch_pairs[:3]}..." if len(batch_pairs) > 3 else f"Batch lookup pairs: {batch_pairs}", "DEBUG")

        batch_resp = self.jsonrpc.get_movies_by_title_year_batch(batch_pairs) or {}
        batch_movies = (batch_resp.get("result") or {}).get("movies") or []
        utils.log(f"JSON-RPC returned {len(batch_movies)} movies from batch lookup", "DEBUG")

        # Build a simple matcher key: (normalized_title, year_int)
        def _key(t, y):
            nt = (t or "").strip().lower()
            try:
                yi = int(y or 0)
            except Exception:
                yi = 0
            return (nt, yi)

        # Index returned movies by (title,year) and also title-only as fallback
        idx_ty = {}
        idx_t = {}
        for m in batch_movies:
            kty = _key(m.get("title"), m.get("year"))
            idx_ty.setdefault(kty, []).append(m)
            kt = _key(m.get("title"), 0)
            idx_t.setdefault(kt, []).append(m)

        # Rebuild resolved list in the original refs order (already sorted by search score from query)
        for i, item in enumerate(rows): # Use original 'rows' to get 'id' and 'source' for unmatched items
            ref_title = item.get("title", "") # Get title from original row if available
            ref_year = item.get("year", 0) # Get year from original row if available
            ref_imdb = item.get("imdbnumber", "") # Get imdbnumber from original row if available

            k_exact = _key(ref_title, ref_year)
            k_title = _key(ref_title, 0)
            cand = (idx_ty.get(k_exact) or idx_t.get(k_title) or [])
            meta = cand[0] if cand else None

            resolved_item = None
            if meta:
                # Found in Kodi library via JSON-RPC
                # utils.log(f"Item {i+1}: Found Kodi match for '{ref_title}' ({ref_year}) -> '{meta.get('title')}' ({meta.get('year')})", "DEBUG")
                cast = meta.get('cast') or []
                if isinstance(cast, list):
                    cast = [{'name': a.get('name'),
                             'role': a.get('role'),
                             'thumbnail': a.get('thumbnail')} for a in cast]
                meta['cast'] = cast
                if isinstance(meta.get('writer'), list):
                    meta['writer'] = ' / '.join(meta['writer'])
                # Preserve search score from original item for sorting
                meta['search_score'] = item.get('search_score', 0)
                resolved_item = meta
            else:
                # No Kodi match found - using fallback data
                fallback_title = ref_title or 'Unknown Title'
                utils.log(f"Item {i+1}: No Kodi match for '{ref_title}' ({ref_year}), using fallback title: '{fallback_title}'", "WARNING")
                # Keep unmatched items for now - they're acceptable
                if not resolved_item:
                    resolved_item = {
                        'id': item.get('id'),
                        'title': f"[Unmatched] {ref_title or ref_imdb or 'Unknown'}",
                        'year': ref_year or 0,
                        'plot': f"IMDb ID: {ref_imdb} - Not found in Kodi library" if ref_imdb else "Not found in Kodi library",
                        'rating': 0.0,
                        'kodi_id': None,
                        'file': None,
                        'genre': '',
                        'cast': [],
                        'art': {},
                        'search_score': item.get('search_score', 0)
                    }

            # Ensure a resolved item exists before appending
            if resolved_item:
                resolved.append(resolved_item)

        # Sort external items by search score as well if they have scores
        external_sorted = sorted(external, key=lambda x: x.get('search_score', 0), reverse=True)
        
        return resolved + external_sorted