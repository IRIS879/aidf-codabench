<management>
    <div class="resource-shell">
        <div class="resource-hero">
            <div>
                <div class="resource-eyebrow">Workspace</div>
                <h1>Resource Management</h1>
                <p>Manage submissions, datasets, tasks, and bundles in one place with the same visual language as the rest of the platform.</p>
            </div>
            <help_button href="https://docs.codabench.org/latest/Organizers/Running_a_benchmark/Resource-Management/"
                         tooltip_position="left center">
            </help_button>
        </div>

        <!--Todo: ultimately decide whether this belongs on tasks:management or dataset:management
                Is currently at both locations-->
        <div class="resource-panel">
            <div class="ui top attached tabular menu resource-tabs">
                <div class="active item" data-tab="submissions">Submissions</div>
                <div class="item" data-tab="datasets">Datasets and programs</div>
                <div class="item" data-tab="tasks">Tasks</div>
                <div class="item" data-tab="bundles">Competition Bundles</div>
            </div>
            <div class="ui active bottom attached tab segment resource-segment" data-tab="submissions">
                <submission-management></submission-management>
            </div>
            <div class="ui bottom attached tab segment resource-segment" data-tab="datasets">
                <data-management></data-management>
            </div>
            <div class="ui bottom attached tab segment resource-segment" data-tab="tasks">
                <task-management></task-management>
            </div>
            <div class="ui bottom attached tab segment resource-segment" data-tab="bundles">
                <bundle-management></bundle-management>
            </div>
        </div>
    </div>

    <script>
        let self = this

        self.on('mount', () => {
            $('.ui.menu .item', self.root).tab()
        })
    </script>

    <style type="text/stylus">
        .resource-shell
            max-width 1240px
            margin 18px auto 0
            padding 0 8px 28px

        .resource-hero
            display flex
            align-items flex-start
            justify-content space-between
            gap 16px
            margin-bottom 18px
            padding 22px 26px
            border 1px solid rgba(15, 35, 95, 0.08)
            border-radius 20px
            background linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%)
            box-shadow 0 14px 36px rgba(18, 37, 77, 0.08)

        .resource-eyebrow
            margin-bottom 8px
            color #4f6b95
            font-size 12px
            font-weight 700
            letter-spacing 0.08em
            text-transform uppercase

        .resource-hero h1
            margin 0 0 8px
            color #163257
            font-size 30px
            font-weight 700

        .resource-hero p
            max-width 760px
            margin 0
            color #60728f
            line-height 1.6

        .resource-panel
            border 1px solid rgba(15, 35, 95, 0.08)
            border-radius 20px
            overflow hidden
            background #ffffff
            box-shadow 0 18px 42px rgba(18, 37, 77, 0.08)

        .resource-tabs.ui.tabular.menu
            margin 0
            padding 14px 14px 0
            border none
            background linear-gradient(180deg, #f7faff 0%, #eef4ff 100%)

        .resource-tabs.ui.tabular.menu .item
            margin 0 10px 0 0
            border none
            border-radius 14px 14px 0 0 !important
            background transparent
            color #5f7190
            font-weight 600
            transition background-color .18s ease, color .18s ease, box-shadow .18s ease

        .resource-tabs.ui.tabular.menu .item.active
            background #ffffff
            color #163257
            box-shadow 0 -1px 0 rgba(15, 35, 95, 0.05), 0 12px 24px rgba(18, 37, 77, 0.08)

        .resource-segment.ui.bottom.attached.tab.segment
            margin 0
            padding 18px
            border none
            background #ffffff

        .resource-shell .rm-toolbar
            display flex
            flex-wrap wrap
            align-items center
            justify-content space-between
            gap 14px
            margin-bottom 18px

        .resource-shell .rm-toolbar-filters
            display flex
            flex-wrap wrap
            align-items center
            gap 10px
            min-width 0

        .resource-shell .rm-toolbar-actions
            display flex
            flex-wrap wrap
            align-items center
            justify-content flex-end
            gap 10px
            margin-left auto

        .resource-shell .ui.icon.input input,
        .resource-shell .ui.dropdown,
        .resource-shell .ui.form input,
        .resource-shell .ui.form textarea,
        .resource-shell .ui.form .selection.dropdown
            border-radius 12px !important

        .resource-shell .ui.icon.input input,
        .resource-shell .ui.form input,
        .resource-shell .ui.form textarea
            border 1px solid rgba(28, 52, 95, 0.12)
            background #fbfdff
            box-shadow inset 0 1px 2px rgba(22, 50, 87, 0.04)

        .resource-shell .ui.checkbox label
            color #516884
            font-weight 500

        .resource-shell .ui.table
            border 1px solid rgba(19, 47, 94, 0.08)
            border-radius 16px
            overflow hidden
            box-shadow 0 10px 26px rgba(18, 37, 77, 0.05)

        .resource-shell .ui.table thead th
            background #f4f8ff
            color #18355b
            font-weight 700
            border-color rgba(19, 47, 94, 0.08)

        .resource-shell .ui.table tbody td
            border-color rgba(19, 47, 94, 0.08)

        .resource-shell .ui.table tbody tr:hover
            background #f9fbff

        .resource-shell .ui.pagination.menu
            border-radius 12px
            box-shadow none

        .resource-shell .ui.button
            border-radius 12px
            font-weight 600

        .resource-shell .ui.green.button,
        .resource-shell .ui.green.buttons .button
            background #1f9d55

        .resource-shell .ui.red.button,
        .resource-shell .ui.red.buttons .button
            background #d64545

        .resource-shell .ui.blue.button,
        .resource-shell .ui.blue.buttons .button,
        .resource-shell .ui.primary.button
            background #2b7de9

        .resource-shell .ui.modal
            border-radius 18px

        .resource-shell .ui.modal > .header
            padding 20px 22px
            color #163257
            background linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%)

        .resource-shell .ui.modal > .content
            padding 22px

        .resource-shell .ui.modal > .actions
            padding 16px 22px 20px
            background #fbfdff

        @media (max-width: 900px)
            .resource-hero
                padding 18px

            .resource-hero h1
                font-size 25px

            .resource-segment.ui.bottom.attached.tab.segment
                padding 14px

        @media (max-width: 700px)
            .resource-tabs.ui.tabular.menu
                padding 12px 12px 0
                overflow-x auto

            .resource-tabs.ui.tabular.menu .item
                white-space nowrap

            .resource-shell .rm-toolbar
                align-items stretch

            .resource-shell .rm-toolbar-actions
                width 100%
                justify-content stretch

            .resource-shell .rm-toolbar-actions > .ui.button
                flex 1 1 220px
    </style>

</management>
