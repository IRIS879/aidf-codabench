<submission-upload>
    <div class="ui sixteen wide column submission-container">

        <div class="submission-form">
            <div class="ui grid middle aligned">
                <div class="sixteen wide column">
                    <h1 style="margin: 0;">Submission upload</h1>
                </div>
            </div>

            <div class="ui segment" style="margin-top: 16px;" if="{ opts.competition && opts.competition.enable_model_card_submission }">
                <div style="font-weight: 600; margin-bottom: 6px;">Model Card Templates</div>
                <div style="margin-bottom: 12px; color: rgba(0,0,0,.6);">
                    Download a template to prepare your model card, or simply fill in the form below.
                </div>
                <a class="ui button"
                   style="background:#e0e1e2; color:rgba(0,0,0,.6); margin-bottom:4px;"
                   href="/static/model-cards/model_card_template.docx"
                   target="_blank"
                   rel="noopener noreferrer">
                    <i class="download icon"></i>
                    DOCX Template
                </a>
                <a class="ui button"
                   style="background:#e0e1e2; color:rgba(0,0,0,.6); margin-bottom:4px;"
                   href="/static/model-cards/model_card_template.json"
                   target="_blank"
                   rel="noopener noreferrer">
                    <i class="download icon"></i>
                    JSON Template
                </a>
                <a class="ui button"
                   style="background:#e0e1e2; color:rgba(0,0,0,.6); margin-bottom:4px;"
                   href="/static/model-cards/model_card_template.md"
                   target="_blank"
                   rel="noopener noreferrer">
                    <i class="download icon"></i>
                    Markdown Template
                </a>
            </div>

            <div if="{_.get(selected_phase, 'status') === 'Previous'}" class="ui red message">
                This phase has ended and no longer accepts submissions!
            </div>

            <div if="{_.get(selected_phase, 'status') === 'Next'}" class="ui yellow message">
                This phase hasn't started yet!
            </div>

            <form class="ui form coda-animated {error: errors}" ref="form" enctype="multipart/form-data">

                <div class="submission-form" ref="fact_sheet_form" if="{ opts.fact_sheet !== null}">
                    <h2>Metadata or Fact Sheet</h2>
                    <div class="submission-form-question" each="{ question in opts.fact_sheet }">

                        <span if="{ question.type === 'text' }">
                            <label if="{question.is_required == 'true'}" class="required-answer">{ question.title }:</label>
                            <label if="{question.is_required == 'false'}">{ question.title }:</label>
                            <input type="text" name="{ question.key }">
                        </span>

                        <span if="{ question.type === 'checkbox' }">
                            <label>{ question.title }:</label>
                            <input type="hidden" name="{ question.key }" value="false">
                            <input type="checkbox" name="{ question.key }" value="true">
                        </span>

                        <span if="{ question.type === 'selection' }">
                            <label if="{question.is_required == 'true'}" class="required-answer">{ question.title }:</label>
                            <label if="{question.is_required == 'false'}">{ question.title }:</label>
                            <select class="ui dropdown" name="{ question.key }">
                                <option value="">Select</option>
                                <option each="{ option in question.options }" value="{ option }">{ option }</option>
                            </select>
                        </span>

                    </div>
                </div>

                <div class="field" if="{ organizations && organizations.length }">
                    <label>Organization</label>
                    <select class="ui dropdown" ref="organization_dropdown">
                        <option value="">None</option>
                        <option each="{ org in organizations }" value="{ org.id }">{ org.name }</option>
                        <option value="new_organization">+ Add New Organization</option>
                    </select>
                </div>

                <div class="field submission-upload-section">
                    <div class="upload-block">
                        <label class="upload-label">Submission ZIP</label>
                        <input-file
                            name="data_file"
                            ref="data_file"
                            error="{errors.data_file}"
                            accept=".zip">
                        </input-file>
                    </div>

                    <!-- Model card section — only shown when the competition requires it -->
                    <div class="upload-block model-card-block" if="{ opts.competition && opts.competition.enable_model_card_submission }">
                        <label class="upload-label">
                            Model Card
                            <span class="mc-required-star">*</span>
                        </label>

                        <!-- Tab switcher -->
                        <div class="ui secondary pointing menu mc-tab-menu">
                            <a class="item { active: mc_mode === 'form' }"
                               onclick="{ set_mc_mode_form }">
                                Fill Form
                            </a>
                            <a class="item { active: mc_mode === 'upload' }"
                               onclick="{ set_mc_mode_upload }">
                                Upload File
                            </a>
                        </div>

                        <!-- Form fill mode -->
                        <div class="mc-panel" if="{ mc_mode === 'form' }">
                            <div class="mc-field">
                                <label>Model Name <span class="mc-required-star">*</span></label>
                                <input class="mc-input" type="text" ref="mc_model_name" placeholder="e.g. Cox-PH Baseline">
                            </div>
                            <div class="mc-field">
                                <label>Task <span class="mc-required-star">*</span></label>
                                <input class="mc-input" type="text" ref="mc_task" placeholder="e.g. Survival prediction">
                            </div>
                            <div class="mc-field">
                                <label>Output <span class="mc-required-star">*</span></label>
                                <input class="mc-input" type="text" ref="mc_output" placeholder="e.g. Risk score per horizon (1–60 months)">
                            </div>
                            <div class="mc-field">
                                <label>Overview <span class="mc-required-star">*</span></label>
                                <textarea class="mc-textarea" ref="mc_overview" rows="4"
                                    placeholder="Briefly describe the purpose of the model and the problem it is designed to solve."></textarea>
                            </div>
                            <div class="mc-error" if="{ errors.model_card_form_data }">{ errors.model_card_form_data }</div>
                        </div>

                        <!-- File upload mode -->
                        <div class="mc-panel" if="{ mc_mode === 'upload' }">
                            <div style="font-size:12px; color:rgba(0,0,0,.5); margin-bottom:6px;">
                                Accepted formats: .pdf &nbsp;·&nbsp; .json &nbsp;·&nbsp; .md / .markdown
                            </div>
                            <input-file
                                name="model_card_file"
                                ref="model_card_file"
                                error="{errors.model_card_file}"
                                accept=".pdf,application/pdf,.json,.md,.markdown">
                            </input-file>
                        </div>
                    </div>
                </div>

        <div class="field" style="margin-top: 24px;">
            <button
                type="button"
                class="ui button"
                onclick="{check_form}"
                disabled="{is_submitting || _.get(selected_phase, 'status') !== 'Current'}">
                { is_submitting ? 'Submitting...' : 'Submit' }
            </button>
        </div>

            </form>
        </div>

        <div class="ui indicating progress" ref="progress">
            <div class="bar">
                <div class="progress">{ upload_progress }%</div>
            </div>
        </div>

        <div class="ui message error" show="{ Object.keys(errors).length > 0 }">
            <div class="header">Error(s) uploading submission</div>
            <ul class="list">
                <li each="{ error, field in errors }">
                    <strong>{ field }:</strong> { error }
                </li>
            </ul>
        </div>

        <div class="ui styled fluid accordion submission-output-container">

            <div class="title active">
                <i class="dropdown icon"></i>
                Submission logs
            </div>

            <div class="content active">

                <div id="submission-output" ref="submission_output" class="ui segment coda-animated">

                    <div class="submission-tabs ui top attached tabular menu">
                        <a class="item active" onclick="{select_tab}" data-tab="prediction">Prediction</a>
                        <a class="item" onclick="{select_tab}" data-tab="scoring">Scoring</a>
                    </div>

                    <div class="ui bottom attached tab segment active" data-tab="prediction">
                        <log_window
                            selected_submission="{selected_submission}"
                            selected_tab="prediction"
                            detailed_result_url="{get_detailed_result_url()}"
                            show_graph="{opts.competition.enable_detailed_results}">
                        </log_window>
                    </div>

                    <div class="ui bottom attached tab segment" data-tab="scoring">
                        <log_window
                            selected_submission="{selected_submission}"
                            selected_tab="scoring"
                            detailed_result_url="{get_detailed_result_url()}"
                            show_graph="{opts.competition.enable_detailed_results}">
                        </log_window>
                    </div>

                    <div class="ui checkbox" ref="autoscroll_checkbox" style="margin-top: 10px;">
                        <input type="checkbox" onchange="{toggle_autoscroll}">
                        <label>Auto-scroll logs</label>
                    </div>

                </div>

            </div>

        </div>

    </div>

<script>
    var self = this
    self.mixin(ProgressBarMixin)

    self.errors = {}
    self.selected_submission = {}
    self.selected_phase = {}
    self.selected_tasks = []
    self.upload_progress = 0
    self.autoscroll_selected = false
    self.children = []
    self.organizations = []
    self.detailed_result_urls = {}
    self.is_submitting = false

    // 'form' = fill-in-page, 'upload' = file upload
    self.mc_mode = 'form'

    self.set_mc_mode_form = function () {
        self.mc_mode = 'form'
        self.update()
    }

    self.set_mc_mode_upload = function () {
        self.mc_mode = 'upload'
        self.update()
    }

    self.on("mount", function () {
        console.log("[submission-upload] mounted")
        console.log("[submission-upload] opts.competition =", opts.competition)
        console.log("[submission-upload] opts.fact_sheet =", opts.fact_sheet)

        if (self.refs.organization_dropdown) {
            $(self.refs.organization_dropdown).dropdown()
        }
    })

    self.get_detailed_result_url = function () {
        if (!self.selected_submission || !self.selected_submission.id) {
            return null
        }
        return self.detailed_result_urls[self.selected_submission.id] || null
    }

    self.clear_form = function () {
        console.log("[submission-upload] clear_form")

        $(':input', self.refs.form)
            .not(':button, :submit, :reset, :hidden')
            .val('')
            .removeAttr('checked')
            .removeAttr('selected')

        var prediction_input = self.refs.data_file && self.refs.data_file.refs ? self.refs.data_file.refs.file_input : null
        var model_card_input = self.refs.model_card_file && self.refs.model_card_file.refs ? self.refs.model_card_file.refs.file_input : null

        if (prediction_input) {
            prediction_input.value = ''
        }
        if (model_card_input) {
            model_card_input.value = ''
        }

        // Clear model card form fields
        if (self.refs.mc_model_name) self.refs.mc_model_name.value = ''
        if (self.refs.mc_task)       self.refs.mc_task.value = ''
        if (self.refs.mc_output)     self.refs.mc_output.value = ''
        if (self.refs.mc_overview)   self.refs.mc_overview.value = ''

        self.errors = {}
        self.update()
    }

    self.collect_fact_sheet_answers = function () {
        var answers = {}

        if (!opts.fact_sheet) {
            console.log("[submission-upload] no fact sheet configured")
            return answers
        }

        opts.fact_sheet.forEach(function (question) {
            var elements = self.refs.form.querySelectorAll('[name="' + question.key + '"]')

            if (!elements || !elements.length) {
                answers[question.key] = ''
                return
            }

            if (question.type === 'checkbox') {
                var checked = false
                for (var i = 0; i < elements.length; i++) {
                    if (elements[i].type === 'checkbox' && elements[i].checked) {
                        checked = true
                        break
                    }
                }
                answers[question.key] = checked
                return
            }

            answers[question.key] = elements[0].value
        })

        console.log("[submission-upload] fact_sheet_answers =", answers)
        return answers
    }

    self.check_form = function (event) {
        if (event) {
            event.preventDefault()
        }

        console.log("[submission-upload] CHECK_FORM fired")
        console.log("[submission-upload] selected_phase =", self.selected_phase)

        self.file_upload_progress_handler(undefined)
        self.errors = {}

        if (!self.selected_phase || self.selected_phase.status !== 'Current') {
            console.warn("[submission-upload] Phase is not current")
            toastr.warning("This phase is not accepting submissions")
            return
        }

        var prediction_input = self.refs.data_file && self.refs.data_file.refs ? self.refs.data_file.refs.file_input : null
        var prediction_file = prediction_input && prediction_input.files ? prediction_input.files[0] : null

        var model_card_input = self.refs.model_card_file && self.refs.model_card_file.refs ? self.refs.model_card_file.refs.file_input : null
        var model_card_file = model_card_input && model_card_input.files ? model_card_input.files[0] : null

        console.log("[submission-upload] prediction_input =", prediction_input)
        console.log("[submission-upload] prediction_file =", prediction_file)
        console.log("[submission-upload] prediction size =", prediction_file ? prediction_file.size : null)
        console.log("[submission-upload] prediction type =", prediction_file ? prediction_file.type : null)

        console.log("[submission-upload] model_card_input =", model_card_input)
        console.log("[submission-upload] model_card_file =", model_card_file)
        console.log("[submission-upload] model_card size =", model_card_file ? model_card_file.size : null)
        console.log("[submission-upload] model_card type =", model_card_file ? model_card_file.type : null)

        if (!prediction_file) {
            self.errors.data_file = "Please select a submission ZIP file"
        } else if (!prediction_file.name.toLowerCase().endsWith('.zip')) {
            self.errors.data_file = "Prediction file must be a .zip"
        }

        var mc_required = opts.competition && opts.competition.enable_model_card_submission
        if (mc_required) {
            if (self.mc_mode === 'upload') {
                // File upload mode
                if (!model_card_file) {
                    self.errors.model_card_file = "Please select a model card file"
                } else {
                    var mc_name = model_card_file.name.toLowerCase()
                    var mc_ok = mc_name.endsWith('.pdf') || mc_name.endsWith('.json') ||
                                mc_name.endsWith('.md') || mc_name.endsWith('.markdown')
                    if (!mc_ok) {
                        self.errors.model_card_file = "Accepted: .pdf, .json, .md, .markdown"
                    }
                }
            } else {
                // Form fill mode
                var mc_model_name = self.refs.mc_model_name ? self.refs.mc_model_name.value.trim() : ''
                var mc_task       = self.refs.mc_task       ? self.refs.mc_task.value.trim()       : ''
                var mc_output     = self.refs.mc_output     ? self.refs.mc_output.value.trim()     : ''
                var mc_overview   = self.refs.mc_overview   ? self.refs.mc_overview.value.trim()   : ''
                var mc_missing = []
                if (!mc_model_name) mc_missing.push('Model Name')
                if (!mc_task)       mc_missing.push('Task')
                if (!mc_output)     mc_missing.push('Output')
                if (!mc_overview)   mc_missing.push('Overview')
                if (mc_missing.length) {
                    self.errors.model_card_form_data = "Please fill in: " + mc_missing.join(', ')
                }
            }
        }

        if (opts.fact_sheet) {
            var fact_sheet_answers = self.collect_fact_sheet_answers()

            opts.fact_sheet.forEach(function (question) {
                var value = fact_sheet_answers[question.key]
                var isEmpty = value === '' || value === null || value === undefined

                if (question.is_required === 'true' && isEmpty) {
                    self.errors[question.key] = question.title + " is required"
                }
            })
        }

        if (Object.keys(self.errors).length > 0) {
            console.warn("[submission-upload] Form validation failed", self.errors)
            self.update()
            return
        }

        console.log("[submission-upload] CHECK_FORM passed")
        console.log("[submission-upload] phase id =", self.selected_phase && self.selected_phase.id)
        console.log("[submission-upload] prediction filename =", prediction_file && prediction_file.name)
        console.log("[submission-upload] model card filename =", model_card_file && model_card_file.name)
        console.log("[submission-upload] mc_mode =", self.mc_mode)

        self.upload()
    }

    self.upload = function () {
        try {
            console.log("[submission-upload] UPLOAD started")

            self.is_submitting = true
            self.update()

            var prediction_input = self.refs.data_file && self.refs.data_file.refs ? self.refs.data_file.refs.file_input : null
            var prediction_file = prediction_input && prediction_input.files ? prediction_input.files[0] : null

            var model_card_input = self.refs.model_card_file && self.refs.model_card_file.refs ? self.refs.model_card_file.refs.file_input : null
            var model_card_file = model_card_input && model_card_input.files ? model_card_input.files[0] : null

            var mc_required = opts.competition && opts.competition.enable_model_card_submission

            console.log("[submission-upload] upload prediction_input =", prediction_input)
            console.log("[submission-upload] upload prediction_file =", prediction_file)
            console.log("[submission-upload] upload prediction size =", prediction_file ? prediction_file.size : null)
            console.log("[submission-upload] upload prediction type =", prediction_file ? prediction_file.type : null)
            console.log("[submission-upload] upload mc_required =", mc_required)
            console.log("[submission-upload] upload mc_mode =", self.mc_mode)
            console.log("[submission-upload] upload model_card_input =", model_card_input)
            console.log("[submission-upload] upload model_card_file =", model_card_file)

            if (!prediction_file) {
                console.error("[submission-upload] No prediction file found inside upload()")
                self.errors.data_file = "Please select a submission ZIP file"
                self.is_submitting = false
                self.update()
                return
            }

            var mc_form_data_json = null
            if (mc_required && self.mc_mode === 'form') {
                // Build form data from input refs
                var mc_model_name = self.refs.mc_model_name ? self.refs.mc_model_name.value.trim() : ''
                var mc_task       = self.refs.mc_task       ? self.refs.mc_task.value.trim()       : ''
                var mc_output_val = self.refs.mc_output     ? self.refs.mc_output.value.trim()     : ''
                var mc_overview   = self.refs.mc_overview   ? self.refs.mc_overview.value.trim()   : ''
                mc_form_data_json = JSON.stringify({
                    model_name: mc_model_name,
                    task:       mc_task,
                    output:     mc_output_val,
                    overview:   mc_overview
                })
                console.log("[submission-upload] upload mc_form_data_json =", mc_form_data_json)
            } else if (mc_required && self.mc_mode === 'upload') {
                if (!model_card_file) {
                    console.error("[submission-upload] No model card file found inside upload()")
                    self.errors.model_card_file = "Please select a model card file"
                    self.is_submitting = false
                    self.update()
                    return
                }
            }

            var timestamp = new Date().toISOString().replace(/[:.]/g, '-')

            var dataset_metadata = {
                name: timestamp + '__' + prediction_file.name,
                type: 'submission',
                description: 'Competition submission file'
            }

            console.log("[submission-upload] calling create_dataset with metadata =", dataset_metadata)

            var datasetRequest = CODALAB.api.create_dataset(
                dataset_metadata,
                prediction_file,
                self.file_upload_progress_handler
            )

            console.log("[submission-upload] create_dataset returned =", datasetRequest)

            datasetRequest
                .done(function (dataset) {
                    console.log("[submission-upload] create_dataset DONE")
                    console.log("[submission-upload] dataset upload SUCCESS")
                    console.log("[submission-upload] dataset.key =", dataset && dataset.key)
                    console.log("[submission-upload] dataset =", dataset)

                    var formData = new FormData()
                    formData.append('data', dataset.key)
                    formData.append('phase', self.selected_phase.id)

                    // Attach model card payload (file or form data)
                    if (mc_form_data_json) {
                        formData.append('model_card_form_data', mc_form_data_json)
                    } else if (model_card_file) {
                        formData.append('model_card_file', model_card_file)
                    }

                    var fact_sheet_answers = self.collect_fact_sheet_answers()
                    if (opts.fact_sheet && Object.keys(fact_sheet_answers).length > 0) {
                        formData.append('fact_sheet_answers', JSON.stringify(fact_sheet_answers))
                    }

                    if (
                        self.refs.organization_dropdown &&
                        self.refs.organization_dropdown.value &&
                        self.refs.organization_dropdown.value !== 'new_organization'
                    ) {
                        formData.append('organization', self.refs.organization_dropdown.value)
                    }

                    console.log("[submission-upload] FINAL SUBMISSION PAYLOAD")
                    console.log("[submission-upload] phase =", self.selected_phase.id)
                    console.log("[submission-upload] dataset key =", dataset.key)
                    console.log("[submission-upload] model_card_file =", model_card_file ? model_card_file.name : null)
                    console.log("[submission-upload] model_card_size =", model_card_file ? model_card_file.size : null)
                    console.log("[submission-upload] mc_form_data =", mc_form_data_json ? "(form)" : "(none)")

                    try {
                        for (var pair of formData.entries()) {
                            console.log("[submission-upload] formData", pair[0], pair[1])
                        }
                    } catch (e) {
                        console.error("[submission-upload] Could not iterate FormData entries", e)
                    }

                    console.log("[submission-upload] calling multipart POST /api/submissions/")

                    var submissionRequest = $.ajax({
                        url: '/api/submissions/',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        xhr: function () {
                            var xhr = $.ajaxSettings.xhr()
                            if (xhr && xhr.upload) {
                                xhr.upload.addEventListener('progress', function (evt) {
                                    if (evt.lengthComputable) {
                                        self.file_upload_progress_handler(evt)
                                    }
                                }, false)
                            }
                            return xhr
                        }
                    })

                    console.log("[submission-upload] create_submission returned =", submissionRequest)

                    submissionRequest
                        .done(function (submission) {
                            console.log("[submission-upload] create_submission DONE")
                            console.log("[submission-upload] submission =", submission)

                            toastr.success("Submission uploaded successfully")
                            self.selected_submission = submission
                            CODALAB.events.trigger('new_submission_created', submission)
                            CODALAB.events.trigger('submission_selected', submission)
                            self.clear_form()
                            self.update()
                        })
                        .fail(function (response) {
                            console.error("[submission-upload] create_submission FAIL")
                            console.error("[submission-upload] response object =", response)
                            console.error("[submission-upload] HTTP status =", response ? response.status : null)
                            console.error("[submission-upload] statusText =", response ? response.statusText : null)
                            console.error("[submission-upload] raw response =", response ? response.responseText : null)

                            if (response) {
                                try {
                                    var errors = JSON.parse(response.responseText)
                                    Object.keys(errors).forEach(function (key) {
                                        if (Array.isArray(errors[key])) {
                                            errors[key] = errors[key].join('; ')
                                        }
                                    })
                                    console.error("[submission-upload] parsed errors =", errors)
                                    self.errors = errors
                                    if (errors.model_card_file) {
                                        toastr.error(errors.model_card_file)
                                    }
                                    self.update()
                                } catch (e) {
                                    console.error("[submission-upload] create_submission FAIL parse error", e)
                                    toastr.error("Submission creation failed")
                                }
                            } else {
                                toastr.error("Submission creation failed")
                            }
                        })
                        .always(function () {
                            console.log("[submission-upload] create_submission ALWAYS")
                            self.is_submitting = false
                            setTimeout(self.hide_progress_bar, 500)
                            self.update()
                        })
                })
                .fail(function (response) {
                    console.error("[submission-upload] create_dataset FAIL")
                    console.error("[submission-upload] response object =", response)
                    console.error("[submission-upload] HTTP status =", response ? response.status : null)
                    console.error("[submission-upload] statusText =", response ? response.statusText : null)
                    console.error("[submission-upload] raw response =", response ? response.responseText : null)

                    if (response) {
                        try {
                            var errors = JSON.parse(response.responseText)
                            Object.keys(errors).forEach(function (key) {
                                if (Array.isArray(errors[key])) {
                                    errors[key] = errors[key].join('; ')
                                }
                            })
                            console.error("[submission-upload] parsed dataset errors =", errors)
                            self.errors = errors
                            self.update()
                        } catch (e) {
                            console.error("[submission-upload] create_dataset FAIL parse error", e)
                            toastr.error("Submission ZIP upload failed")
                        }
                    } else {
                        toastr.error("Submission ZIP upload failed")
                    }

                    self.is_submitting = false
                    setTimeout(self.hide_progress_bar, 500)
                    self.update()
                })
        } catch (e) {
            console.error("[submission-upload] upload crashed")
            console.error(e)
            self.is_submitting = false
            self.update()
            toastr.error("Upload crashed in browser")
        }
    }

    self.toggle_autoscroll = function () {
        self.autoscroll_selected = !self.autoscroll_selected
        self.autoscroll_output()
    }

    self.select_tab = function (e) {
        var tab = e.item.getAttribute('data-tab')
        $('.submission-tabs .item', self.root).removeClass('active')
        $(e.item).addClass('active')
        $('.tab.segment', self.root).removeClass('active')
        $('.tab.segment[data-tab="' + tab + '"]', self.root).addClass('active')
    }

    CODALAB.events.on('submission_selected', function (selected_submission) {
        console.log("[submission-upload] event submission_selected", selected_submission)
        self.selected_submission = selected_submission
        self.autoscroll_output()
        self.update()
    })

    CODALAB.events.on('phase_selected', function (selected_phase) {
        console.log("[submission-upload] event phase_selected", selected_phase)
        self.selected_phase = selected_phase
        self.update()
    })

    self.autoscroll_output = function () {
        if (!self.refs.autoscroll_checkbox) {
            return
        }
        if (self.autoscroll_selected) {
            var output = self.refs.submission_output
            output.scrollTop = output.scrollHeight
        }
    }
</script>

<style type="text/stylus">
:scope
    display block
    width 100%
    height 100%
    margin-bottom 15px

.required-answer::after
    margin -.2em 0 0 .2em
    content '*'
    color #db2828

.submission-form
    background-color white
    padding 2em
    border solid 1px #dcdcdcdc
    margin-bottom 2em

.submission-form-question
    padding .66em 2em

    label
        font-size 16px
        font-weight 600

.submission-upload-section
    margin-top 2em
    margin-bottom 2em

.upload-block
    margin-top 1em

.upload-label
    display block
    font-size 14px
    font-weight 600
    margin-bottom .5em

.model-card-block
    margin-top 1.5em
    padding 1em 1.2em
    border 1px solid #e0e1e2
    border-radius 4px
    background #fafafa

.mc-required-star
    color #db2828
    margin-left 2px

.mc-tab-menu
    margin-bottom .8em !important
    font-size 13px

.mc-panel
    padding-top .5em

.mc-field
    margin-bottom .8em

    label
        font-size 13px
        font-weight 600
        display block
        margin-bottom 3px
        color rgba(0,0,0,.75)

.mc-input
    width 100%
    padding 6px 8px
    border 1px solid rgba(34,36,38,.15)
    border-radius 3px
    font-size 13px
    outline none
    &:focus
        border-color #85b7d9

.mc-textarea
    width 100%
    padding 6px 8px
    border 1px solid rgba(34,36,38,.15)
    border-radius 3px
    font-size 13px
    resize vertical
    outline none
    &:focus
        border-color #85b7d9

.mc-error
    color #db2828
    font-size 12px
    margin-top 4px

#submission-output
    .submission-tabs
        overflow-x scroll
        padding-bottom 10px

        .item
            border solid 1px #efefef
            cursor pointer

            &:hover
                background-color #f5f5f5

        .item.active
            border solid 1px #03bbbbad

code
    background hsl(220, 80%, 90%)

.submission-container
    margin-top 1em

.hidden
    display none

.submission-output-container
    margin-top 15px

    .ui.basic.segment
        min-height 300px
        display none
        overflow-y auto

.graph-container
    display block
    height 250px
</style>

</submission-upload>
