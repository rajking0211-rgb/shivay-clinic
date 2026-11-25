/* =====================================================
   SHIVAY CLINIC
   ORIGINAL INTERACTIONS
===================================================== */


/* =====================================================
   HEADER
===================================================== */

const header = document.getElementById("header");

window.addEventListener("scroll", () => {

    if (window.scrollY > 30) {
        header.classList.add("scrolled");
    } else {
        header.classList.remove("scrolled");
    }

});


/* =====================================================
   MOBILE NAVIGATION
===================================================== */

const mobileMenu =
    document.getElementById("mobileMenu");

const navigation =
    document.getElementById("navigation");


mobileMenu.addEventListener("click", () => {

    navigation.classList.toggle("open");

    const icon =
        mobileMenu.querySelector("i");

    if (navigation.classList.contains("open")) {

        icon.classList.remove("fa-bars");
        icon.classList.add("fa-xmark");

    } else {

        icon.classList.remove("fa-xmark");
        icon.classList.add("fa-bars");

    }

});


document.querySelectorAll(".nav-link").forEach(link => {

    link.addEventListener("click", () => {

        navigation.classList.remove("open");

        const icon =
            mobileMenu.querySelector("i");

        icon.classList.remove("fa-xmark");
        icon.classList.add("fa-bars");

    });

});


/* =====================================================
   ACTIVE NAVIGATION
===================================================== */

const navLinks =
    document.querySelectorAll(".nav-link");

const pageSections =
    document.querySelectorAll("section[id]");


window.addEventListener("scroll", () => {

    let current = "";

    pageSections.forEach(section => {

        const top =
            section.offsetTop - 160;

        const bottom =
            top + section.offsetHeight;

        if (
            window.scrollY >= top &&
            window.scrollY < bottom
        ) {

            current =
                section.getAttribute("id");

        }

    });


    navLinks.forEach(link => {

        link.classList.remove("active");

        if (
            link.getAttribute("href") ===
            `#${current}`
        ) {

            link.classList.add("active");

        }

    });

});


/* =====================================================
   SCROLL REVEAL
===================================================== */

const revealElements =
    document.querySelectorAll(".reveal");


const revealObserver =
    new IntersectionObserver(

        entries => {

            entries.forEach(entry => {

                if (entry.isIntersecting) {

                    entry.target.classList.add("visible");

                    revealObserver.unobserve(
                        entry.target
                    );

                }

            });

        },

        {
            threshold: 0.12
        }

    );


revealElements.forEach(element => {

    revealObserver.observe(element);

});


/* =====================================================
   APPOINTMENT MODAL
===================================================== */

const appointmentModal =
    document.getElementById("appointmentModal");

const openAppointmentButtons =
    document.querySelectorAll(
        "[data-open-appointment]"
    );

const closeModalElements =
    document.querySelectorAll(
        "[data-close-modal]"
    );


function openAppointment() {

    appointmentModal.classList.add("open");

    appointmentModal.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add("modal-open");

}


function closeAppointment() {

    appointmentModal.classList.remove("open");

    appointmentModal.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove("modal-open");

}


openAppointmentButtons.forEach(button => {

    button.addEventListener(
        "click",
        openAppointment
    );

});


closeModalElements.forEach(element => {

    element.addEventListener(
        "click",
        closeAppointment
    );

});


document.addEventListener("keydown", event => {

    if (
        event.key === "Escape" &&
        appointmentModal.classList.contains("open")
    ) {

        closeAppointment();

    }

});


/* =====================================================
   APPOINTMENT FORM
===================================================== */

const appointmentForm =
    document.getElementById("appointmentForm");

const appointmentSuccess =
    document.getElementById("appointmentSuccess");

const appointmentDate =
    document.getElementById("appointmentDate");


/* Prevent past dates */

const now = new Date();

const currentYear =
    now.getFullYear();

const currentMonth =
    String(now.getMonth() + 1)
        .padStart(2, "0");

const currentDay =
    String(now.getDate())
        .padStart(2, "0");

const minimumDate =
    `${currentYear}-${currentMonth}-${currentDay}`;

appointmentDate.min = minimumDate;


appointmentForm.addEventListener(
    "submit",
    async event => {

        event.preventDefault();


        const name =
            document
                .getElementById("patientName")
                .value
                .trim();

        const phone =
            document
                .getElementById("patientPhone")
                .value
                .trim();

        const email =
            document
                .getElementById("patientEmail")
                .value
                .trim();

        const specialty =
            document
                .getElementById(
                    "appointmentSpecialty"
                )
                .value;

        const date =
            document
                .getElementById("appointmentDate")
                .value;


        if (
            !name ||
            !email ||
            !phone ||
            !specialty ||
            !date
        ) {

            alert(
                "Please complete all required fields."
            );

            return;

        }


        /* Phone validation */

        const phonePattern =
            /^[0-9+\-\s()]{10,15}$/;


        if (!phonePattern.test(phone)) {

            alert(
                "Please enter a valid phone number."
            );

            return;

        }


        const submitButton =
            appointmentForm.querySelector(
                "[type='submit']"
            );

        const appointmentError =
            document.getElementById(
                "appointmentError"
            );

        appointmentError.textContent = "";
        appointmentSuccess.classList.remove("show");
        submitButton.disabled = true;

        try {

            const response =
                await fetch("/api/enquiries", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        name,
                        email,
                        phone,
                        specialty,
                        date,
                        message: document
                            .getElementById("appointmentMessage")
                            .value
                            .trim()
                    })
                });

            const result =
                await response.json();

            if (!response.ok) {
                throw new Error(
                    result.error ||
                    "We couldn't send your request. Please call the clinic."
                );
            }

            appointmentSuccess.querySelector("span").textContent =
                result.message;
            appointmentSuccess.classList.add("show");
            appointmentForm.reset();
            appointmentDate.min = minimumDate;

            setTimeout(() => {
                appointmentSuccess.classList.remove("show");
            }, 6000);

        } catch (error) {

            appointmentError.textContent =
                error.message ||
                "We couldn't send your request. Please call the clinic.";

        } finally {

            submitButton.disabled = false;

        }

    }

);


/* =====================================================
   DOCTOR FILTER
===================================================== */

const doctorFilters =
    document.getElementById("doctorFilters");

const doctorGrid =
    document.getElementById("doctorGrid");

const appointmentSpecialty =
    document.getElementById("appointmentSpecialty");

const fallbackDoctors = [
    {
        name: "Dr. Arjun Sharma",
        specialty: "General Medicine",
        qualifications: "MBBS, MD · General Physician",
        years_experience: 12,
        rating: 4.9
    },
    {
        name: "Dr. Neha Kapoor",
        specialty: "Cardiology",
        qualifications: "MBBS, MD, DM · Cardiologist",
        years_experience: 10,
        rating: 4.9
    },
    {
        name: "Dr. Rohan Mehta",
        specialty: "Orthopedics",
        qualifications: "MBBS, MS · Orthopedic Specialist",
        years_experience: 14,
        rating: 4.8
    },
    {
        name: "Dr. Riya Mehta",
        specialty: "Pediatrics",
        qualifications: "MBBS, MD · Pediatrician",
        years_experience: 8,
        rating: 4.9
    }
];


function specialtySlug(specialty) {

    return specialty
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");

}


function addDoctorText(parent, tagName, className, text) {

    const element =
        document.createElement(tagName);

    if (className) {
        element.className = className;
    }

    element.textContent = text;
    parent.appendChild(element);
    return element;

}


function createDoctorCard(doctor, index) {

    const specialtyKey =
        specialtySlug(doctor.specialty);

    const card =
        document.createElement("article");

    card.classList.add("doctor-card", "reveal", "visible");
    card.dataset.specialty = specialtyKey;

    const image =
        document.createElement("div");

    image.classList.add(
        "doctor-image",
        `doctor-bg-${["one", "two", "three", "four"][index % 4]}`
    );

    const avatar =
        document.createElement("div");

    avatar.className = "doctor-avatar";

    const avatarIcon =
        document.createElement("i");

    avatarIcon.className = "fa-solid fa-user-doctor";
    avatar.appendChild(avatarIcon);
    image.appendChild(avatar);

    if (doctor.image_url) {
        const photo =
            document.createElement("img");

        photo.className = "doctor-photo";
        photo.src = doctor.image_url;
        photo.alt = doctor.name;
        image.appendChild(photo);
    }

    addDoctorText(
        image,
        "span",
        "doctor-specialty",
        doctor.specialty
    );
    card.appendChild(image);

    const details =
        document.createElement("div");

    details.className = "doctor-details";
    addDoctorText(details, "h3", "", doctor.name);
    addDoctorText(
        details,
        "p",
        "",
        doctor.qualifications
    );

    const info =
        document.createElement("div");

    info.className = "doctor-info-row";

    [
        ["fa-briefcase", `${doctor.years_experience}+ Years`],
        ["fa-star", Number(doctor.rating).toFixed(1)]
    ].forEach(([iconName, label]) => {

        const item =
            document.createElement("span");

        const icon =
            document.createElement("i");

        icon.className = `fa-solid ${iconName}`;
        item.append(icon, document.createTextNode(` ${label}`));
        info.appendChild(item);

    });

    details.appendChild(info);

    if (doctor.bio) {
        addDoctorText(
            details,
            "p",
            "doctor-bio",
            doctor.bio
        );
    }

    const button =
        document.createElement("button");

    button.className = "doctor-book";
    button.dataset.doctor = doctor.name;
    button.dataset.specialty = doctor.specialty;
    button.append(
        document.createTextNode("View Profile "),
        Object.assign(document.createElement("i"), {
            className: "fa-solid fa-arrow-right"
        })
    );

    details.appendChild(button);
    card.appendChild(details);
    return card;

}


function applyDoctorFilter(selected) {

    doctorFilters
        .querySelectorAll(".doctor-filter")
        .forEach(button => {
            button.classList.toggle(
                "active",
                button.dataset.filter === selected
            );
        });

    doctorGrid
        .querySelectorAll(".doctor-card")
        .forEach(card => {
            card.classList.toggle(
                "hidden",
                selected !== "all" &&
                card.dataset.specialty !== selected
            );
        });

}


doctorFilters.addEventListener("click", event => {

    const filter =
        event.target.closest(".doctor-filter");

    if (filter) {
        applyDoctorFilter(filter.dataset.filter);
    }

});


doctorGrid.addEventListener("click", event => {

    const button =
        event.target.closest(".doctor-book");

    if (!button) {
        return;
    }

    openAppointment();
    document.getElementById("appointmentMessage").value =
        `I would like to consult ${button.dataset.doctor}.`;

    const option =
        Array.from(appointmentSpecialty.options)
            .find(item => item.value === button.dataset.specialty);

    if (option) {
        appointmentSpecialty.value = option.value;
    }

});


async function loadDoctors() {

    try {

        const response =
            await fetch("/api/doctors");

        if (!response.ok) {
            throw new Error(
                `Doctor API returned HTTP ${response.status}.`
            );
        }

        const doctors =
            await response.json();

        if (
            !Array.isArray(doctors) ||
            doctors.some(doctor =>
                !doctor ||
                typeof doctor.name !== "string" ||
                typeof doctor.specialty !== "string" ||
                typeof doctor.qualifications !== "string"
            )
        ) {
            throw new Error("Doctor API returned invalid data.");
        }

        renderDoctors(doctors);

    } catch (error) {

        console.warn(
            "Unable to load managed doctor profiles; showing the default profiles.",
            error
        );
        renderDoctors(fallbackDoctors);

    }

}


function renderDoctors(doctors) {

    doctorGrid.replaceChildren();
    doctorFilters
        .querySelectorAll(".doctor-filter:not([data-filter='all'])")
        .forEach(filter => filter.remove());

    const specialties =
        [...new Set(doctors.map(doctor => doctor.specialty))];

    specialties.forEach(specialty => {

        const filter =
            document.createElement("button");

        filter.className = "doctor-filter";
        filter.dataset.filter = specialtySlug(specialty);
        filter.textContent = specialty;
        doctorFilters.appendChild(filter);

        if (![...appointmentSpecialty.options]
            .some(option => option.value === specialty)) {

            appointmentSpecialty.add(
                new Option(specialty, specialty)
            );

        }

    });

    doctors.forEach((doctor, index) => {
        doctorGrid.appendChild(
            createDoctorCard(doctor, index)
        );
    });

    applyDoctorFilter("all");

}


loadDoctors();


/* =====================================================
   FIND CARE SEARCH
===================================================== */

const careSearch =
    document.getElementById(
        "careSearch"
    );

const searchCare =
    document.getElementById(
        "searchCare"
    );

const specialtyCards =
    document.querySelectorAll(
        ".specialty-card"
    );


function performCareSearch() {

    const query =
        careSearch.value
            .trim()
            .toLowerCase();


    if (!query) {

        careSearch.focus();

        return;

    }


    let found = false;


    specialtyCards.forEach(card => {

        const text =
            card.innerText.toLowerCase();

        if (text.includes(query)) {

            card.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });

            card.style.boxShadow =
                "0 0 0 3px rgba(8,127,140,0.18)";

            setTimeout(() => {

                card.style.boxShadow = "";

            }, 1800);

            found = true;

        }

    });


    if (!found) {

        alert(
            `No exact match found for "${careSearch.value}".`
        );

    }

}


searchCare.addEventListener(
    "click",
    performCareSearch
);


careSearch.addEventListener(
    "keydown",
    event => {

        if (event.key === "Enter") {

            performCareSearch();

        }

    }
);


/* =====================================================
   POPULAR SEARCH BUTTONS
===================================================== */

document
    .querySelectorAll("[data-search]")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                careSearch.value =
                    button.dataset.search;

                performCareSearch();

            }
        );

    });


/* =====================================================
   SHOW ALL SPECIALTIES
===================================================== */

const showSpecialties =
    document.getElementById(
        "showSpecialties"
    );


let specialtiesExpanded = false;


showSpecialties.addEventListener(
    "click",
    () => {

        if (!specialtiesExpanded) {

            const extraSpecialties = [

                {
                    icon:
                        "fa-ear-listen",
                    title:
                        "ENT",
                    description:
                        "Specialized care for ear, nose and throat concerns."
                },

                {
                    icon:
                        "fa-tooth",
                    title:
                        "Dental Care",
                    description:
                        "Preventive and general dental healthcare for the whole family."
                },

                {
                    icon:
                        "fa-person-walking",
                    title:
                        "Physiotherapy",
                    description:
                        "Movement, rehabilitation and recovery-focused care."
                }

            ];


            extraSpecialties.forEach(
                specialty => {

                    const card =
                        document.createElement(
                            "article"
                        );


                    card.className =
                        "specialty-card reveal visible";


                    card.innerHTML = `

                        <div class="specialty-top">

                            <div class="specialty-icon">

                                <i class="fa-solid ${specialty.icon}"></i>

                            </div>

                            <span class="specialty-number">
                                +
                            </span>

                        </div>

                        <h3>
                            ${specialty.title}
                        </h3>

                        <p>
                            ${specialty.description}
                        </p>

                        <a href="#doctors">

                            Explore care

                            <i class="fa-solid fa-arrow-right"></i>

                        </a>

                    `;


                    document
                        .getElementById(
                            "specialtyGrid"
                        )
                        .appendChild(card);

                }
            );


            showSpecialties.innerHTML = `
                Show fewer specialties
                <i class="fa-solid fa-arrow-up"></i>
            `;


            specialtiesExpanded = true;

        } else {

            const cards =
                document.querySelectorAll(
                    "#specialtyGrid .specialty-card"
                );


            cards.forEach((card, index) => {

                if (index >= 6) {

                    card.remove();

                }

            });


            showSpecialties.innerHTML = `
                View all specialties
                <i class="fa-solid fa-arrow-right"></i>
            `;


            specialtiesExpanded = false;

        }

    }
);


/* =====================================================
   TESTIMONIAL SLIDER
===================================================== */

const testimonialTrack =
    document.getElementById(
        "testimonialTrack"
    );

const testimonials =
    document.querySelectorAll(
        ".testimonial"
    );

const testimonialPrev =
    document.getElementById(
        "testimonialPrev"
    );

const testimonialNext =
    document.getElementById(
        "testimonialNext"
    );

const sliderDots =
    document.getElementById(
        "sliderDots"
    );


let currentSlide = 0;


/* Create dots */

testimonials.forEach(
    (_, index) => {

        const dot =
            document.createElement(
                "button"
            );

        dot.className =
            "slider-dot";

        dot.setAttribute(
            "aria-label",
            `Testimonial ${index + 1}`
        );


        if (index === 0) {

            dot.classList.add(
                "active"
            );

        }


        dot.addEventListener(
            "click",
            () => {

                currentSlide =
                    index;

                updateTestimonial();

            }
        );


        sliderDots.appendChild(dot);

    }
);


const dots =
    document.querySelectorAll(
        ".slider-dot"
    );


function updateTestimonial() {

    testimonialTrack.style.transform =
        `translateX(-${currentSlide * 100}%)`;


    dots.forEach(
        (dot, index) => {

            dot.classList.toggle(
                "active",
                index === currentSlide
            );

        }
    );

}


testimonialNext.addEventListener(
    "click",
    () => {

        currentSlide++;

        if (
            currentSlide >=
            testimonials.length
        ) {

            currentSlide = 0;

        }

        updateTestimonial();

    }
);


testimonialPrev.addEventListener(
    "click",
    () => {

        currentSlide--;

        if (currentSlide < 0) {

            currentSlide =
                testimonials.length - 1;

        }

        updateTestimonial();

    }
);


/* Auto rotate */

let testimonialTimer =
    setInterval(
        () => {

            currentSlide++;

            if (
                currentSlide >=
                testimonials.length
            ) {

                currentSlide = 0;

            }

            updateTestimonial();

        },
        6000
    );


const testimonialSlider =
    document.querySelector(
        ".testimonial-slider"
    );


testimonialSlider.addEventListener(
    "mouseenter",
    () => {

        clearInterval(
            testimonialTimer
        );

    }
);


testimonialSlider.addEventListener(
    "mouseleave",
    () => {

        testimonialTimer =
            setInterval(
                () => {

                    currentSlide++;

                    if (
                        currentSlide >=
                        testimonials.length
                    ) {

                        currentSlide = 0;

                    }

                    updateTestimonial();

                },
                6000
            );

    }
);


/* =====================================================
   BACK TO TOP
===================================================== */

const backTop =
    document.getElementById(
        "backTop"
    );


window.addEventListener(
    "scroll",
    () => {

        if (window.scrollY > 600) {

            backTop.classList.add(
                "show"
            );

        } else {

            backTop.classList.remove(
                "show"
            );

        }

    }
);


backTop.addEventListener(
    "click",
    () => {

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });

    }
);


/* =====================================================
   SMOOTH INTERNAL LINKS
===================================================== */

document
    .querySelectorAll(
        'a[href^="#"]'
    )
    .forEach(anchor => {

        anchor.addEventListener(
            "click",
            event => {

                const targetId =
                    anchor.getAttribute(
                        "href"
                    );


                if (
                    !targetId ||
                    targetId === "#"
                ) {

                    return;

                }


                const target =
                    document.querySelector(
                        targetId
                    );


                if (!target) {

                    return;

                }


                event.preventDefault();


                const headerHeight =
                    header.offsetHeight;


                const position =
                    target.offsetTop -
                    headerHeight;


                window.scrollTo({

                    top: position,

                    behavior: "smooth"

                });

            }
        );

    });


/* =====================================================
   CURRENT YEAR
===================================================== */

document.getElementById(
    "year"
).textContent =
    new Date().getFullYear();


/* =====================================================
   INITIAL HERO ANIMATION
===================================================== */

window.addEventListener(
    "load",
    () => {

        document
            .querySelectorAll(
                ".hero .reveal"
            )
            .forEach(
                (element, index) => {

                    setTimeout(
                        () => {

                            element.classList.add(
                                "visible"
                            );

                        },
                        index * 180
                    );

                }
            );

    }
);