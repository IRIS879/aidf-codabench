<competition-management>
    <section class="management-shell">
        <div class="management-hero">
            <div class="management-copy">
                <div class="management-kicker">TEST WORKSPACE</div>
                <h1 class="management-title">Manage your tests</h1>
                <p class="management-summary">
                    Create new test spaces, update active evaluations, and keep your submissions flow organized in one place.
                </p>
            </div>
            <div class="management-actions">
                <a class="ui button management-action secondary" href="{ URLS.COMPETITION_UPLOAD }">
                    <i class="upload icon"></i>
                    <span>Upload Test</span>
                </a>
                <a class="ui button management-action primary" href="{ URLS.COMPETITION_ADD }">
                    <i class="add square icon"></i>
                    <span>Create Test</span>
                </a>
            </div>
        </div>
        <competition-list></competition-list>
    </section>

    <script>
        var self = this

    </script>

    <style type="text/stylus">
        .management-shell
            max-width 1240px
            margin 0 auto 56px
            padding 0 24px

        .management-hero
            display flex
            align-items flex-end
            justify-content space-between
            gap 24px
            padding 22px 0 28px

        .management-copy
            max-width 720px

        .management-kicker
            color #6f89aa
            font-size 12px
            font-weight 800
            letter-spacing 0.12em
            text-transform uppercase

        .management-title
            margin 12px 0 10px
            color #102947
            font-size 44px
            line-height 1.08
            font-weight 800

        .management-summary
            margin 0
            color #557195
            font-size 17px
            line-height 1.7

        .management-actions
            display flex
            align-items center
            gap 12px
            flex-wrap wrap

        .management-action.ui.button
            display inline-flex
            align-items center
            gap 8px
            border-radius 999px
            padding 14px 20px
            font-size 14px
            font-weight 800
            box-shadow 0 14px 26px rgba(16, 41, 71, 0.08)

        .management-action.primary
            background linear-gradient(180deg, #1d5aa7, #133f77)
            color #fff

        .management-action.secondary
            background linear-gradient(180deg, #ffab2e, #ff9800)
            color #fff

        @media only screen and (max-width: 767px)
            .management-shell
                padding 0 16px

            .management-hero
                align-items flex-start
                flex-direction column

            .management-title
                font-size 34px
    </style>
</competition-management>
