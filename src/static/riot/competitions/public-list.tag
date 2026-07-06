<public-list>
  <section class="public-tests-shell">
    <div class="page-header">
      <div class="page-header-copy">
        <p class="page-kicker">Test Directory</p>
        <h2 class="page-title">Browse public tests</h2>
        <p class="page-summary">Search the catalog, refine the list, and open a test page to inspect requirements before you submit.</p>
      </div>
      <div class="action-buttons">
        <a class="create-btn create-btn-secondary" href="{ URLS.COMPETITION_UPLOAD }">
          <i class="bi bi-cloud-arrow-up-fill me-1"></i> Upload Test
        </a>
        <a class="create-btn" href="{ URLS.COMPETITION_ADD }">
          <i class="bi bi-plus-square-fill me-1"></i> Create Test
        </a>
      </div>
    </div>

    <div class="content-container">
      <aside class="filters-panel">
        <div class="filters-card-header">
          <h3>Filters</h3>
          <button class="clear-filters-btn" show="{should_show_clear_filters()}" onclick="{clear_all_filters}">Clear all</button>
        </div>

        <div class="filter-group">
          <label class="filter-label" for="search-title">Search by title</label>
          <div class="ui input">
            <input type="text" id="search-title" oninput="{on_title_input}" placeholder="Search tests...">
          </div>
        </div>

        <div class="filter-group">
          <span class="filter-label">Order</span>
          <label><input type="radio" name="order" value="popular" onchange="{set_ordering}"> Most popular</label>
          <label><input type="radio" name="order" value="recent" onchange="{set_ordering}"> Recently added</label>
          <label><input type="radio" name="order" value="with_most_submissions" onchange="{set_ordering}"> Most submissions</label>
        </div>

        <div class="filter-group">
          <span class="filter-label">Your view</span>
          <label><input type="checkbox" onchange="{toggle_participating}"> Participating in</label>
          <label><input type="checkbox" onchange="{toggle_organizing}"> Organizing</label>
        </div>

        <div class="filter-group">
          <span class="filter-label">Other</span>
          <label><input type="checkbox" onchange="{toggle_has_reward}"> Has reward</label>
        </div>
      </aside>

      <div class="list-panel">
        <div class="results-topbar">
          <div class="results-count">
            <strong>{competitions.count || 0}</strong> public tests
          </div>
          <div class="results-hint">Open a card to review requirements, resources, and submission details.</div>
        </div>

        <div id="loading" class="loading-indicator" show="{!competitions}">
          <div class="spinner"></div>
        </div>

        <div class="test-grid">
          <a each="{competition in competitions.results}" class="test-card" href="../{competition.id}">
            <div class="test-card-top">
              <div class="test-card-brand">
                <div class="ui square tiny bordered image img-wrapper">
                  <img src="{competition.logo_icon ? competition.logo_icon : competition.logo}" loading="lazy">
                </div>
                <div class="test-card-headings">
                  <h4 class="heading">{competition.title}</h4>
                  <p class="organizer">Managed by <strong>{competition.created_by}</strong></p>
                </div>
              </div>
              <div class="test-card-date">{pretty_date(competition.created_when)}</div>
            </div>

            <p class="comp-description">{ pretty_description(competition.description) }</p>

            <div class="test-card-footer">
              <div class="test-meta-pill">
                <strong>{competition.submissions_count || 0}</strong> submissions
              </div>
              <div class="test-meta-icons">
                <span class="meta-icon" if="{competition.reward}">
                  <img width="22" height="22" src="/static/img/trophy.png">
                </span>
                <span class="meta-icon" if="{competition.report}">
                  <img width="22" height="22" src="/static/img/paper.png">
                </span>
              </div>
            </div>
          </a>
        </div>

        <div class="no-results-message" if="{competitions.results && competitions.results.length === 0}">
          <div class="ui warning message">
            <div class="header">No tests found</div>
            Try changing your filters or search term.
          </div>
        </div>

        <div class="pagination-nav" if="{competitions.next || competitions.previous}">
          <button show="{competitions.previous}" onclick="{handle_ajax_pages.bind(this, -1)}" class="ui inline button active">Back</button>
          <button hide="{competitions.previous}" disabled="disabled" class="ui inline button disabled">Back</button>
          <span class="pagination-state">{ current_page } of {Math.ceil(competitions.count/competitions.page_size)}</span>
          <button show="{competitions.next}" onclick="{handle_ajax_pages.bind(this, 1)}" class="ui inline button active">Next</button>
          <button hide="{competitions.next}" disabled="disabled" class="ui inline button disabled">Next</button>
        </div>
      </div>
    </div>
  </section>

  <script>
    var self = this
    self.search_timer = null
    self.competitions = {}

    self.filter_state = {
        search: '',
        ordering: '',
        participating_in: false,
        organizing: false,
        has_reward: false
    }

    self.on_title_input = function(e) {
        const value = e.target.value
        self.filter_state.search = value
        self.update()

        if (self.search_timer) {
            clearTimeout(self.search_timer)
        }

        self.search_timer = setTimeout(() => {
            self.update_competitions_list(1)
        }, 1000)
    }

    self.set_ordering = function (e) {
        self.filter_state.ordering = e.target.value
        self.update()
        self.update_competitions_list(1)
    }

    self.toggle_participating = function(e) {
        self.filter_state.participating_in = e.target.checked
        self.update()
        self.update_competitions_list(1)
    }

    self.toggle_organizing = function(e) {
        self.filter_state.organizing = e.target.checked
        self.update()
        self.update_competitions_list(1)
    }

    self.toggle_has_reward = function(e) {
        self.filter_state.has_reward = e.target.checked
        self.update()
        self.update_competitions_list(1)
    }

    self.should_show_clear_filters = function () {
        const { search, ordering, participating_in, organizing, has_reward } = self.filter_state
        return search || ordering || participating_in || organizing || has_reward
    }

    self.clear_all_filters = function() {
        self.filter_state = {
            search: '',
            ordering: '',
            participating_in: false,
            organizing: false,
            has_reward: false
        }

        document.getElementById('search-title').value = ''
        document.querySelectorAll('input[name="order"]').forEach(r => r.checked = false)
        document.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = false)

        self.update_competitions_list(1)
    }

    self.one("mount", function () {
        const urlParams = new URLSearchParams(window.location.search)

        if (urlParams.has("ordering")) {
            const ordering = urlParams.get("ordering")
            if (["popular", "recent"].includes(ordering)) {
                self.filter_state.ordering = ordering
                const radio = document.querySelector(`input[name="order"][value="${ordering}"]`)
                if (radio) radio.checked = true
            }
        }

        self.update_competitions_list(self.get_url_page_number_or_default())
    })

    self.handle_ajax_pages = function (num) {
        $('.pagination-nav > button').prop('disabled', true)
        self.update_competitions_list(self.get_url_page_number_or_default() + num)
    }

    self.update_competitions_list = function (num) {
        self.current_page = num
        $('#loading').show()
        $('.pagination-nav').hide()

        function handleSuccess(response) {
            self.competitions = response
            $('#loading').hide()
            $('.pagination-nav').show()
            history.pushState("", document.title, "?page=" + self.current_page)
            $('.pagination-nav > button').prop('disabled', false)
            self.update()
        }

        return CODALAB.api.get_public_competitions({
            "page": self.current_page,
            "search": self.filter_state.search,
            "ordering": self.filter_state.ordering,
            "participating_in": self.filter_state.participating_in,
            "organizing": self.filter_state.organizing,
            "has_reward": self.filter_state.has_reward
        })
        .fail(function (resp) {
            $('#loading').hide()
            $('.pagination-nav').show()

            let message = "Could not load competition list"
            if (resp.responseJSON && resp.responseJSON.detail) {
                message = resp.responseJSON.detail
            } else if (resp.responseText) {
                try {
                    const json = JSON.parse(resp.responseText)
                    if (json.detail) {
                        message = json.detail
                    }
                } catch (_) {
                    message = resp.responseText
                }
            }
            toastr.error(message)
        })
        .done(handleSuccess)
    }

    self.pretty_date = function (date_string) {
        return !!date_string ? luxon.DateTime.fromISO(date_string).toLocaleString(luxon.DateTime.DATE_FULL) : ''
    }

    self.pretty_description = function (description) {
        return description.substring(0, 120) + (description.length > 120 ? '...' : '') || ''
    }

    self.get_url_page_number_or_default = function () {
        let urlParams = new URLSearchParams(window.location.search)
        if (urlParams.has('page')) {
            let pagenum = parseInt(urlParams.get('page'))
            if (pagenum < 1) {
                history.pushState("test", document.title, "?page=1")
                return 1
            } else {
                return pagenum
            }
        } else {
            history.pushState("test", document.title, "?page=1")
            return 1
        }
    }

    $(window).on('popstate', function () {
        self.update_competitions_list(self.get_url_page_number_or_default())
    })
  </script>

  <style type="text/stylus">
    public-list
      width 100%

    :scope
      display block
      width calc(100% - 3rem)
      max-width 1280px
      margin 0 auto 2rem

    .public-tests-shell
      background linear-gradient(180deg, rgba(255,255,255,0.98), rgba(244,249,255,0.94))
      border 1px solid rgba(12, 79, 150, 0.1)
      border-radius 28px
      box-shadow 0 22px 44px rgba(12, 79, 150, 0.09)
      padding 1.8rem

    .page-header
      display flex
      align-items flex-start
      justify-content space-between
      gap 1.25rem
      margin-bottom 1.6rem

      .page-header-copy
        max-width 720px

      .action-buttons
        display flex
        gap 0.75rem
        flex-wrap wrap

    .page-kicker
      margin 0 0 0.45rem
      color #5d79a0
      text-transform uppercase
      letter-spacing 0.14em
      font-size 0.76rem
      font-weight 700

    .page-title
      margin 0
      font-size 2rem
      font-weight 800
      color #18324a

    .page-summary
      margin 0.6rem 0 0
      max-width 680px
      color #617589
      font-size 1rem
      line-height 1.7

    .create-btn
      font-size 0.95rem
      font-weight 700
      padding 0.85rem 1.15rem
      background linear-gradient(135deg, #0c4f96, #083565)
      color #fff
      text-decoration none
      border-radius 14px
      display inline-flex
      align-items center
      gap 0.45rem
      cursor pointer
      transition transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease
      box-shadow 0 12px 24px rgba(8, 53, 101, 0.18)

      i
        margin-right 0 !important

      &:hover
        background linear-gradient(135deg, #f59d27, #eb8d0a)
        color #fff
        text-decoration none
        transform translateY(-1px)

    .create-btn-secondary
      background linear-gradient(135deg, #f59d27, #eb8d0a)

      &:hover
        background linear-gradient(135deg, #0c4f96, #083565)

    .content-container
      display flex
      width 100%
      gap 1.35rem

    .filters-panel
      width 280px
      flex-shrink 0
      border 1px solid #d8e5f2
      border-radius 22px
      padding 1.2rem
      margin-left 0 !important
      background linear-gradient(180deg, rgba(255,255,255,0.98), rgba(245,249,255,0.92))
      box-shadow 0 18px 40px rgba(12, 79, 150, 0.08)

      .filters-card-header
        display flex
        align-items center
        justify-content space-between
        gap 0.75rem
        margin-bottom 1rem

      h3
        margin 0
        color #18324a
        font-size 1.25rem
        font-weight 800

      input[type="text"]
        width 100%
        padding 0.85rem 0.95rem
        margin 0.35rem 0 0
        border 1px solid #d8e5f2
        border-radius 12px
        background #fdfefe
        color #18324a

      input[type="radio"],
      input[type="checkbox"]
        margin-right 0.45rem

      label
        display block
        color #486072
        font-size 0.95rem
        margin-top 0.7rem
        cursor pointer

    .filter-group
      padding-top 1rem
      margin-top 1rem
      border-top 1px solid #e3edf7

      &:first-of-type
        padding-top 0
        margin-top 0
        border-top none

    .filter-label
      display block
      color #18324a
      font-weight 700
      margin-bottom 0.35rem

    .clear-filters-btn
      display inline-flex
      align-items center
      justify-content center
      border none
      background rgba(12, 79, 150, 0.08)
      color #0c4f96
      border-radius 999px
      padding 0.45rem 0.8rem
      font-size 0.82rem
      font-weight 700
      cursor pointer

      &:hover
        background rgba(12, 79, 150, 0.14)

    .list-panel
      flex 1
      min-width 0

    .results-topbar
      display flex
      align-items center
      justify-content space-between
      gap 1rem
      margin-bottom 1rem
      padding 0 0.15rem

    .results-count
      color #18324a
      font-size 0.96rem

      strong
        font-size 1.1rem
        font-weight 800

    .results-hint
      color #6e8297
      font-size 0.92rem
      text-align right

    .test-grid
      display grid
      grid-template-columns repeat(2, minmax(0, 1fr))
      gap 1rem

    .test-card
      display flex
      flex-direction column
      gap 1rem
      min-height 250px
      height 250px
      padding 1.2rem
      text-decoration none
      background linear-gradient(180deg, rgba(255,255,255,1), rgba(248,251,255,0.96))
      border 1px solid #d8e5f2
      border-radius 24px
      box-shadow 0 18px 36px rgba(12, 79, 150, 0.08)
      transition transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease

      &:hover
        text-decoration none
        transform translateY(-2px)
        border-color rgba(12, 79, 150, 0.28)
        box-shadow 0 24px 44px rgba(12, 79, 150, 0.13)

    .test-card-top
      display flex
      align-items flex-start
      justify-content space-between
      gap 1rem

    .test-card-brand
      display flex
      align-items flex-start
      gap 0.9rem
      min-width 0

    .test-card-headings
      min-width 0

    .img-wrapper
      width 56px !important
      height 56px !important
      min-width 56px
      border-radius 16px !important
      overflow hidden
      border 1px solid #d7e5f3 !important

      img
        object-fit cover
        width 100%
        height 100%

    .heading
      margin 0
      color #18324a
      font-size 1.18rem
      font-weight 800
      line-height 1.25
      display -webkit-box
      -webkit-box-orient vertical
      -webkit-line-clamp 3
      overflow hidden

    .organizer
      margin 0.45rem 0 0
      color #607385
      font-size 0.92rem

      strong
        color #0c4f96

    .test-card-date
      flex 0 0 auto
      padding 0.48rem 0.75rem
      border-radius 999px
      background rgba(12, 79, 150, 0.08)
      color #0c4f96
      font-size 0.82rem
      font-weight 700

    .comp-description
      margin 0
      color #556b80
      line-height 1.72
      font-size 0.95rem
      display -webkit-box
      -webkit-box-orient vertical
      -webkit-line-clamp 3
      overflow hidden

    .test-card-footer
      margin-top auto
      display flex
      align-items center
      justify-content space-between
      gap 1rem

    .test-meta-pill
      display inline-flex
      align-items center
      gap 0.35rem
      padding 0.55rem 0.85rem
      border-radius 999px
      background linear-gradient(135deg, #0c4f96, #083565)
      color white
      font-size 0.88rem
      font-weight 600

      strong
        font-weight 800

    .test-meta-icons
      display flex
      align-items center
      gap 0.55rem

    .meta-icon
      display inline-flex
      align-items center
      justify-content center
      width 34px
      height 34px
      border-radius 999px
      background rgba(245, 157, 39, 0.12)

    .loading-indicator
      display flex
      justify-content center
      padding 2.4rem 0

    .spinner
      width 42px
      height 42px
      border 4px solid rgba(12, 79, 150, 0.14)
      border-top-color #0c4f96
      border-radius 50%
      animation public-list-spin 0.9s linear infinite

    @keyframes public-list-spin
      from
        transform rotate(0deg)
      to
        transform rotate(360deg)

    .no-results-message
      margin-top 1rem

    .pagination-nav
      margin-top 1.25rem
      display flex
      align-items center
      justify-content center
      gap 0.8rem
      text-align center

      .ui.button
        border-radius 12px !important
        background linear-gradient(135deg, #0c4f96, #083565) !important
        color white !important
        font-weight 700 !important
        box-shadow 0 12px 24px rgba(8, 53, 101, 0.18) !important

      .ui.button.disabled
        background #dce7f2 !important
        color #8aa0b7 !important
        box-shadow none !important

    .pagination-state
      color #556b80
      font-weight 700

    @media (max-width: 1100px)
      .page-header
        flex-direction column

      .content-container
        flex-direction column

      .filters-panel
        width 100%

      .test-grid
        grid-template-columns 1fr

      .results-topbar
        flex-direction column
        align-items flex-start

      .results-hint
        text-align left

    @media (max-width: 640px)
      :scope
        width calc(100% - 1.4rem)

      .public-tests-shell
        padding 1.1rem

      .page-title
        font-size 1.6rem

      .test-card
        padding 1rem
        min-height auto
        height auto

      .test-card-top
        flex-direction column

      .action-buttons
        width 100%

      .create-btn
        width 100%
        justify-content center
  </style>
</public-list>
