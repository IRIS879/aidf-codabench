<competition-details>
  <div class="ui form">

    <!-- Title -->
    <div class="field required">
      <label>Title</label>
      <input type="text" ref="title" oninput="{form_updated}">
    </div>

    <!-- Logo (optional) -->
    <div class="field">
      <label>Logo</label>

      <label show="{ uploaded_logo }">
        Uploaded Logo:
        <a href="{ uploaded_logo }" target="_blank">{ uploaded_logo_name }</a>
      </label>

      <div class="ui left action file input">
        <button class="ui icon button" onclick="document.getElementById('logo-input').click()">
          <i class="upload icon"></i>
        </button>
        <input type="text" placeholder="No file selected" readonly value="{ logo_file_name }">
        <input id="logo-input" type="file" ref="logo" style="display:none" accept="image/*">
      </div>
    </div>

    <!-- Competition Type -->
    <div class="field">
      <label>Competition Type</label>
      <select class="ui dropdown" ref="competition_type" onchange="{form_updated}">
        <option value="competition">Competition</option>
        <option value="benchmark">Benchmark</option>
      </select>
    </div>

    <!-- Reward -->
    <div class="field">
      <label>Competition Reward</label>
      <input type="text" ref="reward" oninput="{form_updated}">
    </div>

    <!-- Contact Email -->
    <div class="field">
      <label>Organizer Contact Email</label>
      <input type="email" ref="contact_email" oninput="{form_updated}">
    </div>

    <!-- Report -->
    <div class="field">
      <label>Competition Report</label>
      <input type="text" ref="report" oninput="{form_updated}">
    </div>

    <!-- Description -->
    <div class="field">
      <label>Description</label>
      <textarea ref="comp_description"></textarea>
    </div>

    <!-- Queue -->
    <div class="field">
      <label>Queue</label>
      <select class="ui dropdown" ref="queue" onchange="{form_updated}">
        <option value=""> </option>
        <option each="{ queue in queues }" value="{ queue.id }">{ queue.name }</option>
      </select>
    </div>

    <!-- Docker Image -->
    <div class="field required">
      <label>Competition Docker Image *</label>
      <input
        type="text"
        ref="docker_image"
        oninput="{form_updated}"
        placeholder="codalab/codalab-legacy:py37"
      >
    </div>

    <!-- Terms -->
    <div class="field">
      <label>Terms</label>
      <textarea ref="terms" oninput="{form_updated}"></textarea>
    </div>

  </div>

  <script>
    var self = this
    self.data = {}
    self.logo_file_name = ''
    self.queues = []

    self.one("mount", function () {
      self.markdown_editor = create_easyMDE(self.refs.comp_description)

      // Make description changes trigger save enable
      self.markdown_editor.codemirror.on("change", function () {
        self.form_updated()
      })

      $('.ui.checkbox', self.root).checkbox({
        onChange: self.form_updated
      })

      // Logo upload -> base64
      $(self.refs.logo).change(function () {
        var file = this.files[0]
        if (!file) return

        self.logo_file_name = file.name
        self.update()

        getBase64(file).then(function (data) {
          self.data["logo"] = JSON.stringify({
            file_name: file.name,
            data: data
          })
          self.form_updated()
        })
      })

      $(self.refs.competition_type).dropdown({ onChange: self.form_updated })
      $(self.refs.queue).dropdown({ onChange: self.form_updated })

      self.form_updated()
    })

    self.form_updated = function () {
      // Update data FIRST
      self.data["title"] = self.refs.title.value
      self.data["docker_image"] = self.refs.docker_image.value
      self.data["competition_type"] = self.refs.competition_type.value
      self.data["reward"] = self.refs.reward.value
      self.data["contact_email"] = self.refs.contact_email.value
      self.data["report"] = self.refs.report.value
      self.data["description"] = self.markdown_editor.value()
      self.data["queue"] = self.refs.queue.value || null
      self.data["terms"] = self.refs.terms.value

      // Tell parent form data changed
      self.trigger("form_updated", self.data)

      // VALIDITY — must be AFTER data update
      var is_valid = !!self.data["title"] && !!self.data["docker_image"]
      CODALAB.events.trigger("competition_is_valid_update", "details", is_valid)
    }

    self.on("update_competition_details", function (competition, queues) {
      self.queues = queues || []

      self.refs.title.value = competition.title || ""
      self.refs.docker_image.value = competition.docker_image || "codalab/codalab-legacy:py37"
      self.refs.reward.value = competition.reward || ""
      self.refs.contact_email.value = competition.contact_email || ""
      self.refs.report.value = competition.report || ""
      self.refs.terms.value = competition.terms || ""

      self.logo_file_name = ""
      self.uploaded_logo = competition.logo
      self.uploaded_logo_name = (competition.logo || "").split("/").pop()

      $(self.refs.competition_type).dropdown("set selected", competition.competition_type || "competition")

      if (competition.queue) {
        $(self.refs.queue).dropdown("set selected", competition.queue.id)
      } else {
        $(self.refs.queue).dropdown("clear")
      }

      self.markdown_editor.value(competition.description || "")
      self.form_updated()
      self.update()
    })
  </script>

  <style>
    :scope {
      display: block;
      width: 100%;
    }
  </style>
</competition-details>